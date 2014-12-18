from datetime import datetime, timedelta
from sqlalchemy import func
from inbox.config import config
from inbox.contacts.process_mail import update_contacts_from_message
from inbox.models import Message, Thread, Part, ActionLog
from inbox.models.action_log import schedule_action
from inbox.sqlalchemy_ext.util import generate_public_id


DEFAULT_DAILY_SENDING_LIMIT = 300


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
    sendmail_cls = getattr(sendmail_mod, sendmail_mod.SENDMAIL_CLS)
    sendmail_client = sendmail_cls(account.id)
    return sendmail_client


def get_draft(db_session, account, draft_public_id):
    """ Get the draft with public_id = `draft_public_id`, or None. """
    return db_session.query(Message).join(Thread).filter(
        Message.public_id == draft_public_id,
        Thread.namespace_id == account.namespace.id).first()


def create_draft(db_session, account, to_addr=None, subject=None,
                 body=None, blocks=None, cc_addr=None, bcc_addr=None,
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
    is_reply = replyto_thread is not None

    return create_and_save_draft(db_session, account, to_addr, subject, body,
                                 blocks, cc_addr, bcc_addr, tags,
                                 replyto_thread, is_reply, syncback=syncback)


def update_draft(db_session, account, original_draft, to_addr=None,
                 subject=None, body=None, blocks=None, cc_addr=None,
                 bcc_addr=None, tags=None):
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

    def update(attr, value=None):
        if value is not None:
            setattr(original_draft, attr, value)

            if attr == 'sanitized_body':
                # Update size, snippet too
                original_draft.size = len(value)
                original_draft.snippet = original_draft.calculate_html_snippet(
                    value)

    update('to_addr', to_addr)
    update('cc_addr', cc_addr)
    update('bcc_addr', bcc_addr)
    update('subject', subject if subject else None)
    update('sanitized_body', body if body else None)
    update('received_date', datetime.utcnow())

    # Remove any attachments that aren't specified
    new_block_ids = [b.id for b in blocks]
    for part in filter(lambda x: x.block_id not in new_block_ids,
                       original_draft.parts):
        original_draft.parts.remove(part)
        db_session.delete(part)

    # Parts, tags require special handling
    for block in blocks:
        # Don't re-add attachments that are already attached
        if block.id in [p.block_id for p in original_draft.parts]:
            continue
        part = Part(block=block)
        part.namespace_id = account.namespace.id
        part.content_disposition = 'attachment'
        part.is_inboxapp_attachment = True
        original_draft.parts.append(part)

        db_session.add(part)

    thread = original_draft.thread
    if tags:
        tags_to_keep = {tag for tag in thread.tags if not tag.user_created}
        thread.tags = tags | tags_to_keep

    # Remove previous message-contact associations, and create new ones.
    original_draft.contacts = []
    update_contacts_from_message(db_session, original_draft, account.namespace)

    # Delete previous version on remote
    schedule_action('delete_draft', original_draft,
                    original_draft.namespace.id, db_session,
                    inbox_uid=original_draft.inbox_uid,
                    message_id_header=original_draft.message_id_header)

    # Update version  + inbox_uid (is_created is already set)
    version = generate_public_id()
    update('version', version)
    update('inbox_uid', version)

    # Sync to remote
    schedule_action('save_draft', original_draft, original_draft.namespace.id,
                    db_session)

    db_session.commit()

    return original_draft


def delete_draft(db_session, account, draft_public_id):
    """ Delete the draft with public_id = `draft_public_id`. """
    draft = db_session.query(Message).filter(
        Message.public_id == draft_public_id).one()
    thread = draft.thread
    namespace = draft.namespace

    assert draft.is_draft

    # Delete remotely.
    schedule_action('delete_draft', draft, draft.namespace.id, db_session,
                    inbox_uid=draft.inbox_uid,
                    message_id_header=draft.message_id_header)

    db_session.delete(draft)

    # Delete the thread if it would now be empty.
    if not thread.messages:
        db_session.delete(thread)
    elif not thread.drafts:
        # Otherwise, remove the drafts tag from the thread if there are no more
        # drafts on it.
        thread.remove_tag(namespace.tags['drafts'])

    db_session.commit()


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
                          syncback=True):
    """Create a draft object and commit it to the database."""
    with db_session.no_autoflush:
        dt = datetime.utcnow()
        uid = generate_public_id()
        version = generate_public_id()
        to_addr = to_addr or []
        cc_addr = cc_addr or []
        bcc_addr = bcc_addr or []
        blocks = blocks or []
        body = body or ''
        if subject is None and thread is not None:
            # Set subject from thread by default.
            subject = thread.subject
        subject = subject or ''

        message = Message()
        message.namespace = account.namespace
        message.is_created = True
        message.is_draft = True
        message.state = 'draft'
        message.from_addr = [(account.name, account.email_address)]
        # TODO(emfree): we should maybe make received_date nullable, so its
        # value doesn't change in the case of a drafted-and-later-reconciled
        # message.
        message.received_date = dt
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
        message.public_id = uid
        message.version = version
        message.inbox_uid = version

        # Set the snippet
        message.snippet = message.calculate_html_snippet(body)

        # Associate attachments to the draft message
        for block in blocks:
            # Create a new Part object to associate to the message object.
            # (You can't just set block.message, because if block is an
            # attachment on an existing message, that would dissociate it from
            # the existing message.)
            part = Part(block=block)
            part.namespace_id = account.namespace.id
            part.content_disposition = 'attachment'
            part.is_inboxapp_attachment = True
            message.parts.append(part)
            db_session.add(part)

        update_contacts_from_message(db_session, message, account.namespace)

        if is_reply:
            message.is_reply = True
            # Construct the in-reply-to and references headers from the last
            # message currently in the thread.
            _set_reply_headers(message, thread)
        if thread is None:
            # Create a new thread object for the draft.
            # We specialize the thread class so that we can, for example, add
            # the g_thrid for Gmail later if we reconcile a synced message with
            # this one. This is a huge hack, but works.
            thread_cls = account.thread_cls
            thread = thread_cls(
                subject=message.subject,
                recentdate=message.received_date,
                namespace=account.namespace,
                subjectdate=message.received_date)
            db_session.add(thread)

        message.thread = thread
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
                new_message.references = (last_message.references +
                                          [last_message.message_id_header])
            else:
                new_message.references = [last_message.message_id_header]


def rate_limited(namespace_id, db_session):
    """Check whether sending for the given namespace should be rate-limited.
    Returns
    -------
    bool
        True if the namespace has exceeded its sending quota.
    """
    max_sends = (config.get('DAILY_SENDING_LIMIT') or
                 DEFAULT_DAILY_SENDING_LIMIT)
    window_start = datetime.utcnow() - timedelta(seconds=86400)
    prior_send_actions, = db_session.query(func.count(ActionLog.id)). \
        filter(ActionLog.namespace_id == namespace_id,
               ActionLog.created_at > window_start,
               ActionLog.action.in_(('send_directly', 'send_draft'))).one()
    return prior_send_actions >= max_sends
