from datetime import datetime
from collections import namedtuple

from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from inbox.server.log import get_logger
log = get_logger(purpose='drafts')
from inbox.server.models.tables.base import SpoolMessage, Thread, DraftThread
from inbox.server.actions.base import save_draft
from inbox.server.sendmail.base import all_recipients
from inbox.server.sendmail.message import create_email, SenderInfo
from inbox.server.sendmail.gmail.gmail import GmailSMTPClient

DraftMessage = namedtuple(
    'DraftMessage', 'uid msg original_draft reply_to date flags')

ReplyToAttrs = namedtuple(
    'ReplyToAttrs', 'subject message_id_header references body')


class SendMailException(Exception):
    pass


def get(db_session, account, draft_public_id):
    """ Get the draft with public_id = draft_public_id. """
    try:
        draft = db_session.query(SpoolMessage).join(Thread).filter(
            SpoolMessage.public_id == draft_public_id,
            Thread.namespace_id == account.namespace.id).one()
    except NoResultFound:
        log.info('NoResultFound for account: {0}, draft_public_id: {1}'.format(
            account.id, draft_public_id))
        return None

    return draft


def get_all(db_session, account):
    """ Get all the draft messages for the account. """
    drafts = []
    try:
        drafts = db_session.query(SpoolMessage).join(Thread).filter(
            SpoolMessage.state == 'draft',
            Thread.namespace_id == account.namespace.id).all()
    except NoResultFound:
        log.info('No drafts found for account: {0}'.format(account.id))
        pass

    return drafts


def new(db_session, account, recipients=None, subject=None, body=None,
        attachments=None):
    """
    Create a new non-reply draft.

    Returns
    -------
    int
        The public_id of the created draft

    """
    sender_info = SenderInfo(name=account.full_name,
                             email=account.email_address)

    draftmsg = _create_gmail_draft(sender_info, recipients, subject,
                                   body, attachments)
    newuid = _save_gmail_draft(db_session, account.id, draftmsg)

    return newuid.message


def reply(db_session, account, thread_public_id, recipients=None, subject=None,
          body=None, attachments=None):
    """
    Create a new reply draft. The thread to reply to is specified by its
    public_id. The draft is created as a reply to the last message
    in the thread.


    Returns
    -------
    int
        The public_id of the created draft

    """
    sender_info = SenderInfo(name=account.full_name,
                             email=account.email_address)

    thread = db_session.query(Thread).filter(
        Thread.public_id == thread_public_id).one()

    draftthread = DraftThread.create(db_session, thread)

    db_session.add(draftthread)
    db_session.commit()

    draftmsg = _create_gmail_draft(sender_info, recipients, subject,
                                   body, attachments,
                                   reply_to=draftthread.id)

    newuid = _save_gmail_draft(db_session, account.id, draftmsg)

    return newuid.message


def update(db_session, account, draft_public_id, recipients=None, subject=None,
           body=None, attachments=None):
    """
    Update the draft with public_id = draft_public_id.

    To maintain our messages are immutable invariant, we create a new draft
    message object.


    Returns
    -------
    int
        The public_id of the updated draft
        Note: This is != draft_public_id.

    """
    sender_info = SenderInfo(name=account.full_name,
                             email=account.email_address)

    draft = SpoolMessage.get_or_copy(db_session, draft_public_id)

    db_session.add(draft)
    db_session.commit()

    # For all these fields: if present in the update request, use the value
    # provided; else, copy from original.
    recipients = recipients or draft.recipients
    subject = subject or draft.subject
    body = body or draft.subject
    attachments = attachments or draft.attachments

    draftmsg = _create_gmail_draft(sender_info, recipients, subject,
                                   body, attachments,
                                   original_draft=draft,
                                   reply_to=draft.replyto_thread_id)
    newuid = _save_gmail_draft(db_session, account.id, draftmsg)

    return newuid.message


def delete(db_session, account, draft_public_id):
    """ Delete the draft with public_id = draft_public_id. """
    draft = db_session.query(SpoolMessage).filter(
        SpoolMessage.public_id == draft_public_id).one()

    _delete_all(db_session, draft.id)


# The logic here is provider agnostic, this function should live
# in a common file.
def _delete_all(db_session, draft_id):
    draft = db_session.query(SpoolMessage).get(draft_id)

    assert draft.is_draft

    if draft.parent_draft_id:
        _delete_all(db_session, draft.parent_draft_id)

    db_session.delete(draft)


# TODO[k]: Attachments handling
def send(db_session, account, draft_public_id):
    """ Send the draft with public_id = draft_public_id. """
    sendmail_client = GmailSMTPClient(account.id, account.namespace)

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

    if not draft.to_addr:
        raise SendMailException("No 'To:' recipients specified!")

    assert len(draft.imapuids) == 1

    concat = lambda xlist: [u'{0} <{1}>'.format(e[0], e[1]) for e in xlist]
    recipients = all_recipients(concat(draft.to_addr), concat(draft.cc_addr),
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


def _create_gmail_draft(sender_info, recipients, subject, body, attachments,
                        original_draft=None, reply_to=None):
    """ Create a draft email message. """
    mimemsg = create_email(sender_info, recipients, subject, body, attachments)

    # The generated `X-INBOX-ID` UUID of the message is too big to serve as the
    # msg_uid for the corresponding ImapUid. The msg_uid is a SQL BigInteger
    # (20 bits), so we truncate the `X-INBOX-ID` to that size. Note that
    # this still provides a large enough ID space to make collisions rare.
    x_inbox_id = mimemsg.headers.get('X-INBOX-ID')
    uid = int(x_inbox_id, 16) & (1 << 20) - 1

    date = datetime.utcnow()
    flags = [u'\\Draft']

    return DraftMessage(uid=uid,
                        msg=mimemsg.to_string(),
                        original_draft=original_draft,
                        reply_to=reply_to,
                        date=date,
                        flags=flags)


def _save_gmail_draft(db_session, account_id, draftmsg):
    """
    Save a draft email message to the local data store and
    sync it to the remote backend too.

    """
    imapuid = save_draft(db_session, log, account_id, draftmsg)
    return imapuid
