"""
These tests verify that messages sent from Inbox are correctly reconciled
with the `Drafts`, `Sent Mail` messages synced from the remote backend during a
subsequent sync - they use the sendmail API calls and then run a sync on the
account to do so.

They do not verify the local data store, see tests/imap/test_sendmail.py or
syncback to the remote backend, tests/imap/network/test_sendmail_syncback.py

"""
import uuid
from datetime import datetime

import pytest
from gevent import Greenlet, kill, getcurrent

from tests.util.crispin import crispin_client
from tests.util.mailsync import sync_client

ACCOUNT_ID = 1
NAMESPACE_ID = 1
THREAD_ID = 16
THREAD_TOPIC = 'Golden Gate Park next Sat'


@pytest.fixture(scope='function')
def message(db, config):
    from inbox.models.tables.imap import ImapAccount

    account = db.session.query(ImapAccount).get(ACCOUNT_ID)
    to = [{'name': u'"\u2605The red-haired mermaid\u2605"',
           'email': account.email_address}]
    subject = 'Draft test: ' + str(uuid.uuid4().hex)
    body = '<html><body><h2>Sea, birds, yoga and sand.</h2></body></html>'

    return (to, subject, body)


@pytest.fixture(autouse=True)
def register_action_backends(db):
    """
    Normally action backends only get registered when the actions
    rqworker starts. So we need to register them explicitly for these
    tests.
    """
    from inbox.actions.base import register_backends
    register_backends()


def test_create_reconcile(db, config, message, sync_client):
    """ Tests the save_draft function, which saves the draft to the remote. """
    from inbox.sendmail.base import create_draft
    from inbox.actions.gmail import remote_save_draft
    from inbox.sendmail.base import _parse_recipients, Recipients
    from inbox.sendmail.message import create_email
    from inbox.models.tables.base import Message, SpoolMessage
    from inbox.models.tables.base import Account

    account = db.session.query(Account).get(ACCOUNT_ID)
    to, subject, body = message
    attachment = None
    cc = None
    bcc = None

    # Store locally
    created = create_draft(db.session, account, to, subject, body,
                           attachment, cc, bcc)
    public_id = created.public_id

    draft_messages = db.session.query(SpoolMessage).filter(
        SpoolMessage.public_id == public_id).all()
    assert len(draft_messages) == 1, 'draft message missing'

    # Store on remote
    date = datetime.utcnow()
    to_addr = _parse_recipients(to)
    recipients = Recipients(to_addr, [], [])
    email = create_email(account.sender_name, account.email_address, public_id,
                         recipients, subject, body, None)
    inbox_uid = email.headers['X-INBOX-ID']
    assert inbox_uid == public_id, \
        'draft to save on remote has incorrect inbox_uid header'

    remote_save_draft(account, account.drafts_folder.name,
                      email.to_string(), db.session, date)

    synclet = Greenlet(sync_client.start_sync, ACCOUNT_ID)
    synclet.start()

    synclet.join(timeout=60)

    print '\nJOINED!'

    r = sync_client.stop_sync(ACCOUNT_ID)
    while r != 'OK sync stopped':
        r = sync_client.stop_sync(ACCOUNT_ID)

    print '\nSTOPPED!'

    synclet.kill()

    print '\nKILLED!'

    # Since the syncing uses its own session, we need to start a new
    # session to see its effects.
    db.new_session()

    spool_messages = db.session.query(SpoolMessage).filter(
        SpoolMessage.public_id == public_id).all()
    assert len(spool_messages) == 1, 'spool_message missing'

    reconciled_message_id = spool_messages[0].resolved_message_id
    assert reconciled_message_id, 'spool message not reconciled'

    reconciled_message = db.session.query(Message).get(reconciled_message_id)
    assert reconciled_message.inbox_uid == public_id,\
        'spool message, reconciled message have different inbox_uids'

    cleanup(db.session, account, subject)

    current = getcurrent()
    kill(current)


def cleanup(db_session, account, subject):
    """ Delete emails in remote. """
    with crispin_client(account.id, account.provider) as c:
        criteria = ['NOT DELETED', 'SUBJECT "{0}"'.format(subject)]

        c.conn.select_folder(account.drafts_folder.name, readonly=False)
        draft_uids = c.conn.search(criteria)
        if draft_uids:
            c.conn.delete_messages(draft_uids)
            c.conn.expunge()
