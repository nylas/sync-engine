from collections import namedtuple

from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from inbox.util.misc import load_modules
from inbox.util.url import NotSupportedError
from inbox.server.log import get_logger
from inbox.server.models import session_scope
from inbox.server.models.tables.base import (SpoolMessage, Thread, DraftThread,
                                             Account, Block)
from inbox.server.sendmail.message import Recipients
from inbox.sqlalchemy.util import b36_to_bin


# Message attributes of a message we're creating a reply to,
# needed to correctly set headers in the reply.
ReplyToAttrs = namedtuple(
    'ReplyToAttrs', 'subject message_id_header references body')


class SendMailException(Exception):
    pass


class SendError(SendMailException):
    def __init__(self, msg=None, failures=None):
        assert msg or failures
        self.msg = msg
        self.failures = failures

    def __str__(self):
        if not self.failures:
            return 'Send failed, message: {0}'.format(self.msg)

        e = ['(to: {0}, error: {1})'.format(k, v[0]) for
             k, v in self.failures.iteritems()]
        return 'Send failed, failures: {0}'.format(', '.join(e))


def register_backends():
    """
    Finds the sendmail modules for the different providers
    (in the sendmail/ directory) and imports them.

    Creates a mapping of provider:sendmail_mod for each backend found.

    """
    import inbox.server.sendmail

    # Find and import
    modules = load_modules(inbox.server.sendmail)

    # Create mapping
    sendmail_mod_for = {}
    for module in modules:
        if hasattr(module, 'PROVIDER'):
            provider = module.PROVIDER

            assert hasattr(module, 'SENDMAIL_CLS')

            sendmail_mod_for[provider] = module

    return sendmail_mod_for


def get_function(provider, fn):
    sendmail_mod_for = register_backends()

    sendmail_mod = sendmail_mod_for.get(provider)
    if not sendmail_mod:
        raise NotSupportedError('Inbox does not support the email provider.')

    return getattr(sendmail_mod, fn, None)


def get_sendmail_client(account):
    sendmail_mod_for = register_backends()

    sendmail_mod = sendmail_mod_for.get(account.provider)
    if not sendmail_mod:
        raise NotSupportedError('Inbox does not support the email provider.')

    sendmail_cls = getattr(sendmail_mod, sendmail_mod.SENDMAIL_CLS)
    sendmail_client = sendmail_cls(account.id, account.namespace)
    return sendmail_client


def _parse_recipients(dicts_list):
    return [(d.get('name', ''), d.get('email', '')) for d in dicts_list]


def all_recipients(to, cc=None, bcc=None):
    """
    Create a Recipients namedtuple.

    Parameters
    ----------
    to : list
        list of utf-8 encoded strings
    cc : list, optional
        list of utf-8 encoded strings
    bcc: list, optional
        list of utf-8 encoded strings

    Returns
    -------
    Recipients(to, cc, bcc)

    """
    if to and not isinstance(to, list):
        to = [to]

    if cc and not isinstance(cc, list):
        cc = [cc]

    if bcc and not isinstance(bcc, list):
        bcc = [bcc]

    return Recipients(to=to, cc=cc, bcc=bcc)


def get_draft(db_session, account, draft_public_id):
    """ Get the draft with public_id = `draft_public_id`, or None. """
    return db_session.query(SpoolMessage).join(Thread).filter(
        SpoolMessage.public_id == draft_public_id,
        Thread.namespace_id == account.namespace.id).first()


def get_all_drafts(db_session, account):
    """ Get all the draft messages for the account. """
    return db_session.query(SpoolMessage).join(Thread).filter(
        SpoolMessage.state == 'draft',
        Thread.namespace_id == account.namespace.id).all()


def create_draft(db_session, account, to=None, subject=None,
                 body=None, block_public_ids=None, cc=None, bcc=None,
                 thread_public_id=None):
    """
    Create a new draft. If `thread_public_id` is specified, the draft is a
    reply to the last message in the thread; otherwise, it is an independant
    draft.

    Returns
    -------
    SpoolMessage
        The created draft message object.

    """
    to_addr = _parse_recipients(to) if to else to
    cc_addr = _parse_recipients(cc) if cc else cc
    bcc_addr = _parse_recipients(bcc) if bcc else bcc
    verify_blocks(block_public_ids, account.namespace.id)

    # For independant drafts
    replyto_thread_id = None

    # For reply drafts
    if thread_public_id is not None:
        thread = db_session.query(Thread).filter(
            Thread.public_id == thread_public_id).one()

        assert thread.namespace == account.namespace

        draft_thread = DraftThread.create(db_session, thread)
        db_session.add(draft_thread)
        db_session.commit()

        replyto_thread_id = draft_thread.id

    create_and_save_fn = get_function(account.provider,
                                      'create_and_save_draft')
    return create_and_save_fn(db_session, account, to_addr, subject, body,
                              block_public_ids, cc_addr, bcc_addr,
                              replyto_thread_id)


def update_draft(db_session, account, draft_public_id, to=None, subject=None,
                 body=None, block_public_ids=None, cc=None, bcc=None):
    """
    Update the draft with public_id = `draft_public_id`.

    To maintain our messages are immutable invariant, we create a new draft
    message object.


    Returns
    -------
    SpoolMessage
        The new draft message object.


    Notes
    -----
    Messages, including draft messages, are immutable in Inbox.
    So to update a draft, we create a new draft message object and
    return its public_id (which is different than the original's).

    """
    draft = SpoolMessage.get_or_copy(db_session, draft_public_id)

    db_session.add(draft)
    db_session.commit()

    to_addr = _parse_recipients(to) if to else draft.to_addr
    cc_addr = _parse_recipients(cc) if cc else draft.cc_addr
    bcc_addr = _parse_recipients(bcc) if bcc else draft.bcc_addr
    subject = subject or draft.subject
    body = body or draft.sanitized_body
    block_public_ids = block_public_ids or \
        [p.public_id for p in draft.parts if p.is_attachment]
    verify_blocks(block_public_ids, account.namespace.id)

    create_and_save_fn = get_function(account.provider,
                                      'create_and_save_draft')
    return create_and_save_fn(db_session, account, to_addr, subject, body,
                              block_public_ids, cc_addr, bcc_addr,
                              draft.replyto_thread_id, draft.id)


def delete_draft(db_session, account, draft_public_id):
    """ Delete the draft with public_id = `draft_public_id`. """
    draft = db_session.query(SpoolMessage).filter(
        SpoolMessage.public_id == draft_public_id).one()

    assert draft.is_draft

    # Delete locally, make sure to delete all previous versions of this draft
    # present locally too.
    _delete_draft_versions(db_session, draft.id)


def _delete_draft_versions(db_session, draft_id):
    draft = db_session.query(SpoolMessage).get(draft_id)

    if draft.parent_draft_id:
        _delete_draft_versions(db_session, draft.parent_draft_id)

    db_session.delete(draft)
    # TODO[k]: Ensure this causes a delete on the remote too for draft of
    # draft_id only!


def send_draft(account_id, draft_id):
    """
    Send the draft with id = `draft_id` or
    if `draft_public_id` is not specified, create a draft and send it - in
    this case, a `to` address must be specified.

    """
    with session_scope() as db_session:
        account = db_session.query(Account).get(account_id)

        log = get_logger(account.id, 'drafts')
        sendmail_client = get_sendmail_client(account)

        try:
            draft = db_session.query(SpoolMessage).filter(
                SpoolMessage.id == draft_id).one()

        except NoResultFound:
            log.info('NoResultFound for draft_id {0}'.format(draft_id))
            raise SendMailException('No draft with id {0}'.format(draft_id))

        except MultipleResultsFound:
            log.info('MultipleResultsFound for draft_id {0}'.format(draft_id))
            raise SendMailException('Multiple drafts with id {0}'.format(
                draft_id))

        assert draft.is_draft and not draft.is_sent

        recipients = Recipients(draft.to_addr, draft.cc_addr, draft.bcc_addr)
        attachment_public_ids = [p.public_id for p in draft.parts
                                 if p.is_attachment]

        if not draft.replyto_thread:
            return sendmail_client.send_new(db_session, draft.imapuids[0],
                                            draft.inbox_uid,
                                            recipients, draft.subject,
                                            draft.sanitized_body,
                                            attachment_public_ids)
        else:
            assert isinstance(draft.replyto_thread, DraftThread)
            thread = draft.replyto_thread.thread

            message_id = draft.replyto_thread.message_id
            if thread.messages[0].id != message_id:
                raise SendMailException(
                    'Can only send a reply to the latest message in thread!')

            thread_subject = thread.subject
            # The first message is the latest message we have for this thread
            message_id_header = thread.messages[0].message_id_header
            # The references are JWZ compliant
            references = thread.messages[0].references
            body = thread.messages[0].prettified_body

            # Encapsulate the attributes of the message to reply to,
            # needed to set the right headers, subject on the reply.
            replyto_attrs = ReplyToAttrs(subject=thread_subject,
                                         message_id_header=message_id_header,
                                         references=references,
                                         body=body)

            return sendmail_client.send_reply(db_session, draft.imapuids[0],
                                              replyto_attrs, draft.inbox_uid,
                                              recipients, draft.subject,
                                              draft.sanitized_body,
                                              attachment_public_ids)


def verify_blocks(block_public_ids, namespace_id):
    """ Verifies that the provided block_public_ids exist and are
        within the given namesapce_id
    """
    if not block_public_ids:
        return
    if not namespace_id:
        raise ValueError("Need a namespace to check!")
    with session_scope() as db_session:
        for block_public_id in block_public_ids:
            try:
                b36_to_bin(block_public_id)
                block = db_session.query(Block).filter(
                    Block.public_id == block_public_id).one()
                assert block.namespace_id == namespace_id
            except (ValueError, NoResultFound, AssertionError):
                raise SendMailException(
                    'The given block public_ids {} are  not part of '
                    'namespace {}'.format(block_public_ids,
                                          namespace_id))


def generate_attachments(block_public_ids):
    if not block_public_ids:
        return
    with session_scope() as db_session:
        all_files = db_session.query(Block).filter(
            Block.public_id.in_(block_public_ids)).all()

        # In the future we may consider discovering the filetype from the data
        # by using #magic.from_buffer(data, mime=True))
        attachments = [
            dict(filename=b.filename,
                 data=b.data,
                 content_type=b.content_type)
            for b in all_files]
        return attachments
