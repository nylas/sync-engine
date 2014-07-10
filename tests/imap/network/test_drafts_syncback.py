import uuid
from datetime import datetime

import pytest

from tests.util.crispin import crispin_client

ACCOUNT_ID = 1
NAMESPACE_ID = 1
THREAD_ID = 2

# These tests use a real Gmail test account and idempotently put the account
# back to the state it started in when the test is done.


@pytest.fixture(scope='function')
def message(db, config):
    from inbox.models.backends.imap import ImapAccount

    account = db.session.query(ImapAccount).get(ACCOUNT_ID)
    to = [{'name': u'"\u2605The red-haired mermaid\u2605"',
           'email': account.email_address}]
    subject = 'Draft test: ' + str(uuid.uuid4().hex)
    body = '<html><body><h2>Sea, birds, yoga and sand.</h2></body></html>'

    return (to, subject, body)


def test_remote_save_draft(db, config, message):
    """ Tests the save_draft function, which saves the draft to the remote. """
    from inbox.actions.gmail import remote_save_draft
    from inbox.sendmail.base import _parse_recipients
    from inbox.sendmail.message import create_email, Recipients
    from inbox.models import Account

    account = db.session.query(Account).get(ACCOUNT_ID)
    to, subject, body = message
    to_addr = _parse_recipients(to)
    recipients = Recipients(to_addr, [], [])
    email = create_email(account.sender_name, account.email_address, None,
                         recipients, subject, body, None)
    date = datetime.utcnow()

    remote_save_draft(account, account.drafts_folder.name, email.to_string(),
                      db.session, date)

    with crispin_client(account.id, account.provider) as c:
        criteria = ['NOT DELETED', 'SUBJECT "{0}"'.format(subject)]

        c.conn.select_folder(account.drafts_folder.name, readonly=False)

        draft_uids = c.conn.search(criteria)
        assert draft_uids, 'Message missing from Drafts folder'

        flags = c.conn.get_flags(draft_uids)
        for uid in draft_uids:
            f = flags.get(uid)
            assert f and '\\Draft' in f, "Message missing '\\Draft' flag"

        c.conn.delete_messages(draft_uids)
        c.conn.expunge()


def test_remote_delete_draft(db, config, message):
    """
    Tests the delete_draft function, which deletes the draft from the
    remote.

    """
    from inbox.actions.gmail import remote_save_draft, remote_delete_draft
    from inbox.sendmail.base import _parse_recipients
    from inbox.sendmail.message import create_email, Recipients
    from inbox.models import Account

    account = db.session.query(Account).get(ACCOUNT_ID)
    to, subject, body = message
    to_addr = _parse_recipients(to)
    recipients = Recipients(to_addr, [], [])
    email = create_email(account.sender_name, account.email_address, None,
                         recipients, subject, body, None)
    date = datetime.utcnow()

    # Save on remote
    remote_save_draft(account, account.drafts_folder.name, email.to_string(),
                      db.session, date)

    inbox_uid = email.headers['X-INBOX-ID']

    with crispin_client(account.id, account.provider) as c:
        criteria = ['DRAFT', 'NOT DELETED',
                    'HEADER X-INBOX-ID {0}'.format(inbox_uid)]

        c.conn.select_folder(account.drafts_folder.name, readonly=False)
        uids = c.conn.search(criteria)
        assert uids, 'Message missing from Drafts folder'

        # Delete on remote
        remote_delete_draft(account, account.drafts_folder.name, inbox_uid,
                            db.session)

        c.conn.select_folder(account.drafts_folder.name, readonly=False)
        uids = c.conn.search(criteria)
        assert not uids, 'Message still in Drafts folder'
