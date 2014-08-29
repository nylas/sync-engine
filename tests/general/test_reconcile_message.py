from datetime import datetime

ACCOUNT_ID = 1
THREAD_ID = 1


def test_reconcile_message(db, config):
    from inbox.models.util import reconcile_message
    from inbox.sendmail.base import create_draft
    from inbox.models.account import Account
    from inbox.models.message import Message

    account = db.session.query(Account).get(ACCOUNT_ID)
    draft = create_draft(db.session, account)

    assert draft.inbox_uid == draft.version, 'draft has incorrect inbox_uid'
    inbox_uid = draft.inbox_uid

    message = Message()
    message.thread_id = THREAD_ID
    message.received_date = datetime.utcnow()
    message.size = len('')
    message.is_draft = True
    message.is_read = True
    message.sanitized_body = ''
    message.snippet = ''
    message.inbox_uid = draft.inbox_uid
    db.session.add(message)
    db.session.commit()

    reconcile_message(db.session, inbox_uid, message)

    assert draft.resolved_message and draft.resolved_message.id == message.id,\
        'draft not reconciled correctly'

    assert message.public_id != draft.public_id, \
        'message has incorrect public_id'
