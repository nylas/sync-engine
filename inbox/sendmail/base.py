from datetime import datetime
from inbox.api.validation import (
    get_recipients, get_tags, get_attachments, get_thread, get_message)
from inbox.api.err import InputError
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
    server_error: string, optional
        The error returned by the mail server.
    failures: dict, optional
        If sending only failed for some recipients, information on the specific
        failures.
    """
    def __init__(self, message, http_code, server_error=None, failures=None):
        self.message = message
        self.http_code = http_code
        self.server_error = server_error
        self.failures = failures

    def __str__(self):
        return self.message


def get_sendmail_client(account):
    from inbox.sendmail import module_registry

    sendmail_mod = module_registry.get(account.provider)
    sendmail_cls = getattr(sendmail_mod, sendmail_mod.SENDMAIL_CLS)
    sendmail_client = sendmail_cls(account)
    return sendmail_client


def create_draft(data, namespace, db_session, syncback):
    """ Construct a draft object (a Message instance) from `data`, a dictionary
    representing the POST body of an API request. All new objects are un-added
    and uncommitted."""

    # Validate the input and get referenced objects (tags, thread, attachments)
    # as necessary.
    to_addr = get_recipients(data.get('to'), 'to')
    cc_addr = get_recipients(data.get('cc'), 'cc')
    bcc_addr = get_recipients(data.get('bcc'), 'bcc')
    subject = data.get('subject')
    if subject is not None and not isinstance(subject, basestring):
        raise InputError('"subject" should be a string')
    body = data.get('body', '')
    if not isinstance(body, basestring):
        raise InputError('"body" should be a string')
    tags = get_tags(data.get('tags'), namespace.id, db_session)
    blocks = get_attachments(data.get('file_ids'), namespace.id, db_session)
    reply_to_thread = get_thread(data.get('thread_id'), namespace.id,
                                 db_session)
    reply_to_message = get_message(data.get('reply_to_message_id'),
                                   namespace.id, db_session)
    if reply_to_message is not None and reply_to_thread is not None:
        if reply_to_message not in reply_to_thread.messages:
            raise InputError('Message {} is not in thread {}'.
                             format(reply_to_message.public_id,
                                    reply_to_thread.public_id))

    with db_session.no_autoflush:
        account = namespace.account
        dt = datetime.utcnow()
        uid = generate_public_id()
        to_addr = to_addr or []
        cc_addr = cc_addr or []
        bcc_addr = bcc_addr or []
        blocks = blocks or []
        if subject is None:
            # If this is a reply with no explicitly specified subject, set the
            # subject from the prior message/thread by default.
            # TODO(emfree): Do we want to allow changing the subject on a reply
            # at all?
            if reply_to_message is not None:
                subject = reply_to_message.subject
            elif reply_to_thread is not None:
                subject = reply_to_thread.subject
        subject = subject or ''

        message = Message()
        message.namespace = namespace
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
        message.public_id = uid
        message.version = 0
        message.regenerate_inbox_uid()

        # Set the snippet
        message.snippet = message.calculate_html_snippet(body)

        # Associate attachments to the draft message
        for block in blocks:
            # Create a new Part object to associate to the message object.
            # (You can't just set block.message, because if block is an
            # attachment on an existing message, that would dissociate it from
            # the existing message.)
            part = Part(block=block)
            part.namespace_id = namespace.id
            part.content_disposition = 'attachment'
            part.is_inboxapp_attachment = True
            message.parts.append(part)
            db_session.add(part)

        update_contacts_from_message(db_session, message, namespace)

        if reply_to_message is not None:
            message.is_reply = True
            _set_reply_headers(message, reply_to_message)
            thread = reply_to_message.thread
            message.reply_to_message = reply_to_message
        elif reply_to_thread is not None:
            message.is_reply = True
            thread = reply_to_thread
            # Construct the in-reply-to and references headers from the last
            # message currently in the thread.
            previous_messages = [m for m in thread.messages if not m.is_draft]
            if previous_messages:
                last_message = previous_messages[-1]
                message.reply_to_message = last_message
                _set_reply_headers(message, last_message)
        else:
            # If this isn't a reply to anything, create a new thread object for
            # the draft.  We specialize the thread class so that we can, for
            # example, add the g_thrid for Gmail later if we reconcile a synced
            # message with this one. This is a huge hack, but works.
            message.is_reply = False
            thread_cls = account.thread_cls
            thread = thread_cls(
                subject=message.subject,
                recentdate=message.received_date,
                namespace=namespace,
                subjectdate=message.received_date)
            if message.attachments:
                attachment_tag = namespace.tags['attachment']
                thread.apply_tag(attachment_tag)

        message.thread = thread
        thread.apply_tag(namespace.tags['drafts'])
        for tag in tags:
            thread.apply_tag(tag)

        if syncback:
            schedule_action('save_draft', message, namespace.id, db_session,
                            version=message.version)
        return message


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
    draft.version += 1
    draft.regenerate_inbox_uid()

    # Sync to remote
    schedule_action('save_draft', draft, draft.namespace.id, db_session,
                    version=draft.version)
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


def _set_reply_headers(new_message, previous_message):
    """When creating a draft in reply to a thread, set the In-Reply-To and
    References headers appropriately, if possible."""
    if previous_message.message_id_header:
        new_message.in_reply_to = previous_message.message_id_header
        if previous_message.references:
            new_message.references = (previous_message.references +
                                      [previous_message.message_id_header])
        else:
            new_message.references = [previous_message.message_id_header]
