from datetime import datetime

from inbox.basicauth import NotSupportedError
from inbox.models import Message, Thread, Part
from inbox.models.action_log import schedule_action
from inbox.sqlalchemy_ext.util import generate_public_id


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


def get_sendmail_client(account):
    from inbox.sendmail import module_registry

    sendmail_mod = module_registry.get(account.provider)
    if not sendmail_mod:
        raise NotSupportedError('Inbox does not support the email provider.')

    sendmail_cls = getattr(sendmail_mod, sendmail_mod.SENDMAIL_CLS)
    sendmail_client = sendmail_cls(account.id)
    return sendmail_client


def _parse_recipients(dicts_list):
    return [(d.get('name', ''), d.get('email', '')) for d in dicts_list]


def get_draft(db_session, account, draft_public_id):
    """ Get the draft with public_id = `draft_public_id`, or None. """
    return db_session.query(Message).join(Thread).filter(
        Message.public_id == draft_public_id,
        Thread.namespace_id == account.namespace.id).first()


def create_draft(db_session, account, to=None, subject=None,
                 body=None, blocks=None, cc=None, bcc=None,
                 tags=None, replyto_thread=None, syncback=True):
    """
    Create a new draft. If `thread_public_id` is specified, the draft is a
    reply to the last message in the thread; otherwise, it is an independant
    draft.

    Returns
    -------
    Message
        The created draft message object.

    """
    to_addr = _parse_recipients(to) if to else to
    cc_addr = _parse_recipients(cc) if cc else cc
    bcc_addr = _parse_recipients(bcc) if bcc else bcc

    is_reply = replyto_thread is not None

    return create_and_save_draft(db_session, account, to_addr, subject, body,
                                 blocks, cc_addr, bcc_addr, tags,
                                 replyto_thread, is_reply, syncback=syncback)


def update_draft(db_session, account, parent_draft, to=None, subject=None,
                 body=None, blocks=None, cc=None, bcc=None, tags=None):
    """
    Update draft.

    To maintain our messages are immutable invariant, we create a new draft
    message object.


    Returns
    -------
    Message
        The new draft message object.


    Notes
    -----
    Messages, including draft messages, are immutable in Inbox.
    So to update a draft, we create a new draft message object and
    return its public_id (which is different than the original's).

    """
    to_addr = _parse_recipients(to) if to else parent_draft.to_addr
    cc_addr = _parse_recipients(cc) if cc else parent_draft.cc_addr
    bcc_addr = _parse_recipients(bcc) if bcc else parent_draft.bcc_addr
    subject = subject or parent_draft.subject
    body = body or parent_draft.sanitized_body
    blocks = blocks or [p for p in parent_draft.parts if p.is_attachment]

    new_draft = create_and_save_draft(db_session, account, to_addr, subject,
                                      body, blocks, cc_addr, bcc_addr, tags,
                                      parent_draft.thread,
                                      parent_draft.is_reply, parent_draft)
    schedule_action('delete_draft', parent_draft, parent_draft.namespace.id,
                    db_session)
    return new_draft


def delete_draft(db_session, account, draft_public_id):
    """ Delete the draft with public_id = `draft_public_id`. """
    draft = db_session.query(Message).filter(
        Message.public_id == draft_public_id).one()

    assert draft.is_draft

    # Delete locally, make sure to delete all previous versions of this draft
    # present locally too.
    _delete_draft_versions(db_session, draft.id)
    # Delete remotely.
    schedule_action('delete_draft', draft, draft.namespace.id, db_session)


def _delete_draft_versions(db_session, draft_id):
    draft = db_session.query(Message).get(draft_id)

    if draft.parent_draft_id:
        _delete_draft_versions(db_session, draft.parent_draft_id)

    db_session.delete(draft)

    # Remove the drafts tag from the thread if there are no more drafts.
    if not draft.thread.latest_drafts:
        draft.thread.remove_tag(draft.namespace.tags['drafts'])


def generate_attachments(blocks):
    attachment_dicts = []
    for block in blocks:
        attachment_dicts.append({
            'filename': block.filename,
            'data': block.data,
            'content_type': block.content_type})
    return attachment_dicts


def create_and_save_draft(db_session, account, to_addr=None, subject=None,
                          body=None, blocks=None, cc_addr=None, bcc_addr=None,
                          new_tags=None, thread=None, is_reply=False,
                          parent_draft=None, syncback=True):
    """
    Create a draft object and commit it to the database.
    """
    dt = datetime.utcnow()
    uid = generate_public_id()
    to_addr = to_addr or []
    cc_addr = cc_addr or []
    bcc_addr = bcc_addr or []
    blocks = blocks or []
    body = body or ''
    if subject is None and thread is not None:
        # Set subject from thread by default.
        subject = thread.subject
    subject = subject or ''

    # Sets is_draft = True, state = 'draft'
    message = Message.create_draft_message()

    message.from_addr = [(account.sender_name, account.email_address)]
    # TODO(emfree): we should maybe make received_date nullable, so its value
    # doesn't change in the case of a drafted-and-later-reconciled message.
    message.received_date = dt
    if parent_draft is not None:
        message.parent_draft_id = parent_draft.id
    message.subject = subject
    message.sanitized_body = body
    message.to_addr = to_addr
    message.cc_addr = cc_addr
    message.bcc_addr = bcc_addr
    # TODO(emfree): this is different from the normal 'size' value of a
    # message, which is the size of the entire MIME message.
    message.size = len(body)
    message.is_read = True
    message.is_sent = False
    message.is_reply = is_reply
    message.inbox_uid = uid
    message.public_id = uid

    # Set the snippet
    message.calculate_html_snippet(body)

    # Associate attachments to the draft message
    for block in blocks:
        # Create a new Part object to associate to the message object.
        # (You can't just set block.message, because if block is an attachment
        # on an existing message, that would dissociate it from the existing
        # message.)
        part = Part()
        part.namespace_id = account.namespace.id
        part.content_disposition = 'attachment'
        part.content_type = block.content_type
        part.is_inboxapp_attachment = True
        part.data = block.data
        part.filename = block.filename
        message.parts.append(part)
        db_session.add(part)

    # TODO(emfree) Update contact data here.

    if is_reply:
        message.is_reply = True
        # If we're updating a draft, copy the in-reply-to and references
        # headers from the parent. Otherwise, construct them from the last
        # message currently in the thread.
        if parent_draft is not None:
            message.in_reply_to = parent_draft.in_reply_to
            message.references = parent_draft.references
        else:
            _set_reply_headers(message, thread)
    if thread is None:
        # Create a new thread object for the draft.
        thread = Thread(
            subject=message.subject,
            recentdate=message.received_date,
            namespace=account.namespace,
            subjectdate=message.received_date)
        db_session.add(thread)

    message.thread = thread
    # This triggers an autoflush, so we need to execute it after setting
    # message.thread
    thread.apply_tag(account.namespace.tags['drafts'])

    if new_tags:
        tags_to_keep = {tag for tag in thread.tags if not tag.user_created}
        thread.tags = new_tags | tags_to_keep

    if syncback:
        schedule_action('save_draft', message, message.namespace.id,
                        db_session)

    db_session.add(message)
    db_session.commit()
    return message


def _set_reply_headers(new_message, thread):
    """When creating a draft in reply to a thread, set the In-Reply-To and
    References headers appropriately, if possible."""
    previous_messages = [m for m in thread.messages if not m.is_draft]
    if previous_messages:
        last_message = previous_messages[-1]
        if last_message.message_id_header:
            new_message.in_reply_to = last_message.message_id_header
            if last_message.references:
                new_message.references = (last_message.references + '\t' +
                                          last_message.message_id_header)
            else:
                new_message.references = last_message.message_id_header
