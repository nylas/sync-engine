from datetime import datetime
from inbox.log import get_logger
from inbox.api.err import err
from inbox.api.kellogs import APIEncoder
from inbox.sendmail.base import get_sendmail_client, SendMailException
log = get_logger()


def send_draft(account, draft, db_session):
    """Send the draft with id = `draft_id`."""
    # Update message state and prepare a response so that we can immediately
    # return it on success, and not potentially have queries fail after
    # sending. Note that changes are flushed here, but committed in the API's
    # after_request handler only on 200 OK (hence only if sending succeeds).
    update_draft_on_send(account, draft, db_session)
    response_on_success = APIEncoder().jsonify(draft)
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

    return response_on_success


def update_draft_on_send(account, draft, db_session):
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
    db_session.flush()


def send_raw_mime(account, db_session, msg):
    recipient_emails = [email for name, email in itertools.chain(
        msg.bcc_addr, msg.cc_addr, msg.to_addr)]
    # Prepare a response so that we can immediately return it on success, and
    # not potentially have queries fail after sending.
    response_on_success = APIEncoder().jsonify(msg)
    try:
        sendmail_client = get_sendmail_client(account)
        sendmail_client.send_raw(msg)

    except SendMailException as exc:
        kwargs = {}
        if exc.failures:
            kwargs['failures'] = exc.failures
        if exc.server_error:
            kwargs['server_error'] = exc.server_error
        return err(exc.http_code, exc.message, **kwargs)

    return response_on_success
