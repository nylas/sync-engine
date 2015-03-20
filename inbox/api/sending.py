from datetime import datetime
from inbox.log import get_logger
from inbox.api.err import err
from inbox.api.kellogs import APIEncoder
from inbox.models.action_log import schedule_action
from inbox.sendmail.base import get_sendmail_client, SendMailException
log = get_logger()


def send_draft(account, draft, db_session, schedule_remote_delete):
    """Send the draft with id = `draft_id`."""
    try:
        sendmail_client = get_sendmail_client(account)
        sendmail_client.send(draft)
    except SendMailException as exc:
        kwargs = {}
        if exc.failures:
            kwargs['failures'] = exc.failures
        if exc.server_error:
            kwargs['server_error'] = exc.server_error
        return err(exc.http_code, exc.message, **kwargs)

    # We want to return success to the API client if the message was sent, even
    # if there are errors in post-send updating. Otherwise the client may think
    # the send has failed. So wrap the rest of the work in try/except.
    try:
        if account.provider == 'icloud':
            # Special case because iCloud doesn't save sent messages.
            schedule_action('save_sent_email', draft, draft.namespace.id,
                            db_session)
        if schedule_remote_delete:
            schedule_action('delete_draft', draft, draft.namespace.id,
                            db_session, inbox_uid=draft.inbox_uid,
                            message_id_header=draft.message_id_header)

        # Update message
        draft.is_sent = True
        draft.is_draft = False
        draft.received_date = datetime.utcnow()

        # Update thread
        sent_tag = account.namespace.tags['sent']
        draft_tag = account.namespace.tags['drafts']
        thread = draft.thread
        thread.apply_tag(sent_tag)
        # Remove the drafts tag from the thread if there are no more drafts.
        if not draft.thread.drafts:
            thread.remove_tag(draft_tag)
        thread.update_from_message(None, draft)
    except Exception as e:
        log.error('Error in post-send processing', error=e, exc_info=True)

    return APIEncoder().jsonify(draft)
