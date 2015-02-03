from datetime import datetime
from inbox.contacts.process_mail import update_contacts_from_message
from inbox.models import Message, Part
from inbox.models.action_log import schedule_action
from inbox.sqlalchemy_ext.util import generate_public_id


class SendMailException(Exception):
    """
    Raised when sending fails.
    Parameters
    ----------
    message: string
        A descriptive error message.
    http_code: int
        An appropriate HTTP error code for the particular type of failure.
    failures: dict, optional
        If sending only failed for some recipients, information on the specific
        failures.
    """
    def __init__(self, message, http_code, failures=None):
        self.message = message
        self.http_code = http_code
        self.failures = failures

    def __str__(self):
        return self.message


def get_sendmail_client(account):
    from inbox.sendmail import module_registry

    sendmail_mod = module_registry.get(account.provider)
    sendmail_cls = getattr(sendmail_mod, sendmail_mod.SENDMAIL_CLS)
    sendmail_client = sendmail_cls(account)
    return sendmail_client


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


def update_draft(db_session, account, draft, to_addr=None,
                 subject=None, body=None, blocks=None, cc_addr=None,
                 bcc_addr=None, tags=None):
    """
    Update draft with new attributes.
    """

    def update(attr, value=None):
        if value is not None:
            setattr(draft, attr, value)

            if attr == 'sanitized_body':
                # Update size, snippet too
                draft.size = len(value)
                draft.snippet = draft.calculate_html_snippet(
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
                       draft.parts):
        draft.parts.remove(part)
        db_session.delete(part)

    # Parts, tags require special handling
    for block in blocks:
        # Don't re-add attachments that are already attached
        if block.id in [p.block_id for p in draft.parts]:
            continue
        part = Part(block=block)
        part.namespace_id = account.namespace.id
        part.content_disposition = 'attachment'
        part.is_inboxapp_attachment = True
        draft.parts.append(part)

        db_session.add(part)

    thread = draft.thread
    if len(thread.messages) == 1:
        # If there are no prior messages on the thread, update its subject and
        # dates to match the draft.
        thread.subject = draft.subject
        thread.subjectdate = draft.received_date
        thread.recentdate = draft.received_date
        attachment_tag = thread.namespace.tags['attachment']
        if draft.attachments:
            thread.apply_tag(attachment_tag)
        else:
            thread.remove_tag(attachment_tag)

    if tags:
        tags_to_keep = {tag for tag in thread.tags if not tag.user_created}
        thread.tags = tags | tags_to_keep

    # Remove previous message-contact associations, and create new ones.
    draft.contacts = []
    update_contacts_from_message(db_session, draft, account.namespace)

    prior_inbox_uid = draft.inbox_uid
    prior_message_id_header = draft.message_id_header

    # Update version  + inbox_uid (is_created is already set)
    version = generate_public_id()
    update('version', version)
    update('inbox_uid', version)

    # Sync to remote
    schedule_action('save_draft', draft, draft.namespace.id,
                    db_session)
    # Delete previous version on remote
    schedule_action('delete_draft', draft,
                    draft.namespace.id, db_session,
                    inbox_uid=prior_inbox_uid,
                    message_id_header=prior_message_id_header)

    db_session.commit()
    return draft


def delete_draft(db_session, account, draft):
    """ Delete the given draft. """
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
            if message.attachments:
                attachment_tag = thread.namespace.tags['attachment']
                thread.apply_tag(attachment_tag)
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
