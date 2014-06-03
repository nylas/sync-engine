from collections import namedtuple
from datetime import datetime

import magic
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from inbox.util.misc import load_modules
from inbox.util.url import NotSupportedError
from inbox.server.crispin import RawMessage
from inbox.server.log import get_logger
from inbox.server.mailsync.backends.base import (create_db_objects,
                                                 commit_uids)
from inbox.server.models.tables.base import SpoolMessage, Thread, DraftThread
from inbox.server.sendmail.message import create_email, SenderInfo, Recipients

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


def _parse_recipients(dicts_list):
    if not (isinstance(dicts_list, list) and
            isinstance(dicts_list[0], dict)):
        return dicts_list

    return [u'{0} <{1}>'.format(d.get('name', ''), d.get('email', ''))
            for d in dicts_list]


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


def create_attachment_metadata(attachments):
    """
    Given local filenames to attach, create the required metadata;
    this includes both file data and file type.

    Parameters
    ----------
    attachments : list
        list of local filenames

    Returns
    -------
    list of dicts
        attachfiles : list of dicts(filename, data, content_type)

    """
    if not attachments:
        return

    attachfiles = []
    for filename in attachments:
        with open(filename, 'rb') as f:
            data = f.read()
            attachfile = dict(filename=filename,
                              data=data,
                              content_type=magic.from_buffer(data, mime=True))

            attachfiles.append(attachfile)

    return attachfiles


def get_draft(db_session, account, draft_public_id):
    """ Get the draft with public_id = draft_public_id. """
    return db_session.query(SpoolMessage).join(Thread).filter(
        SpoolMessage.public_id == draft_public_id,
        Thread.namespace_id == account.namespace.id).first()


def get_all_drafts(db_session, account):
    """ Get all the draft messages for the account. """
    return db_session.query(SpoolMessage).join(Thread).filter(
        SpoolMessage.state == 'draft',
        Thread.namespace_id == account.namespace.id).all()


def create_draft(db_session, account, to=None, subject=None, body=None,
                 attachments=None, cc=None, bcc=None, thread_public_id=None):
    to_addr = _parse_recipients(to) if to else to
    cc_addr = _parse_recipients(cc) if cc else cc
    bcc_addr = _parse_recipients(bcc) if bcc else bcc

    if thread_public_id is not None:
        thread = db_session.query(Thread).filter(
            Thread.public_id == thread_public_id).one()
        assert thread.namespace == account.namespace

        draft_thread = DraftThread.create(db_session, thread)
        db_session.add(draft_thread)
        db_session.commit()
        draft_thread_id = draft_thread.id
    else:
        draft_thread_id = None

    return _create_and_save_draft(db_session, account, to_addr, subject, body,
                                  attachments, cc_addr, bcc_addr,
                                  draft_thread_id)


def update_draft(db_session, account, draft_public_id, to=None, subject=None,
                 body=None, attachments=None, cc=None, bcc=None):
    """
    Update the draft with public_id equal to draft_public_id.

    To maintain our messages are immutable invariant, we create a new draft
    message object.


    Returns
    -------
    SpoolMessage
    The updated draft object.

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

    # TODO(emfree) also handle attachments

    draft_thread_id = draft.replyto_thread_id

    return _create_and_save_draft(db_session, account, to_addr, subject, body,
                                  attachments, cc_addr, bcc_addr,
                                  draft_thread_id, draft.id)


def _create_and_save_draft(db_session, account, to_addr=None, subject=None,
                           body=None, attachments=None, cc_addr=None,
                           bcc_addr=None, draft_thread_id=None,
                           parent_draft_id=None):
    """ Creates a new draft object and commits it to the database.

    Returns
    -------
    The created SpoolMessage instance.
    """
    log = get_logger(account.id, purpose='drafts')

    sender_info = SenderInfo(account.full_name, account.email_address)
    recipients = all_recipients(to_addr, cc_addr, bcc_addr)

    attachments = create_attachment_metadata(attachments)

    mimemsg = create_email(sender_info, recipients, subject, body, attachments)
    msg_body = mimemsg.to_string()

    # The generated `X-INBOX-ID` UUID of the message is too big to serve as the
    # msg_uid for the corresponding ImapUid. The msg_uid is a SQL BigInteger
    # (20 bits), so we truncate the `X-INBOX-ID` to that size. Note that
    # this still provides a large enough ID space to make collisions rare.
    x_inbox_id = mimemsg.headers.get('X-INBOX-ID')
    uid = int(x_inbox_id, 16) & (1 << 20) - 1

    date = datetime.utcnow()
    flags = [u'\\Draft']

    msg = RawMessage(uid=uid, internaldate=date,
                     flags=flags, body=msg_body, g_thrid=None,
                     g_msgid=None, g_labels=set(), created=True)

    message_create_function = get_function(account.provider,
                                           'create_database_message')

    # TODO(emfree): this breaks the 'folders just mirror the backend'
    # assumption we want to be able to make.
    new_uids = create_db_objects(account.id, db_session, log,
                                 account.drafts_folder.name, [msg],
                                 message_create_function)
    new_uid = new_uids[0]

    new_uid.created_date = date

    # Set SpoolMessage's special draft attributes
    new_uid.message.state = 'draft'
    new_uid.message.parent_draft_id = parent_draft_id
    new_uid.message.replyto_thread_id = draft_thread_id

    commit_uids(db_session, log, new_uids)

    return new_uid.message


def delete_draft(db_session, account, draft_public_id):
    """ Delete the draft with public_id = draft_public_id. """
    draft = db_session.query(SpoolMessage).filter(
        SpoolMessage.public_id == draft_public_id).one()

    _delete_all(db_session, draft.id)


def _delete_all(db_session, draft_id):
    draft = db_session.query(SpoolMessage).get(draft_id)

    assert draft.is_draft

    if draft.parent_draft_id:
        _delete_all(db_session, draft.parent_draft_id)

    db_session.delete(draft)


# TODO[k]: Attachments handling
def send_draft(db_session, account, draft_public_id):
    """ Send the draft with public_id equal to draft_public_id. """
    log = get_logger(account.id, 'drafts')
    get_sendmail_client = get_function(account.provider, 'get_sendmail_client')
    sendmail_client = get_sendmail_client(account.id, account.namespace)

    try:
        draft = db_session.query(SpoolMessage).filter(
            SpoolMessage.public_id == draft_public_id).one()
    except NoResultFound:
        log.info('NoResultFound for draft with public_id {0}'.format(
            draft_public_id))
        raise SendMailException('No draft with public_id {0} found'.format(
            draft_public_id))
    except MultipleResultsFound:
        log.info('MultipleResultsFound for draft with public_id {0}'.format(
            draft_public_id))
        raise SendMailException('Multiple drafts with public_id {0} found'.
                                format(draft_public_id))

    assert draft.is_draft and not draft.is_sent

    concat = lambda xlist: [u'{0} <{1}>'.format(e[0], e[1]) for e in xlist]
    recipients = Recipients(concat(draft.to_addr), concat(draft.cc_addr),
                            concat(draft.bcc_addr))
    attachments = None

    if not draft.replyto_thread:
        return sendmail_client.send_new(db_session, draft.imapuids[0],
                                        recipients, draft.subject,
                                        draft.sanitized_body,
                                        attachments)
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
                                          replyto_attrs, recipients,
                                          draft.subject, draft.sanitized_body,
                                          attachments)
