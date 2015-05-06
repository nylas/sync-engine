# test that T441 doesn't reappear, ever.
import datetime
import pytest
from collections import namedtuple
from inbox.auth.generic import GenericAuthHandler
from inbox.models import Folder
from inbox.models.backends.imap import ImapUid
from inbox.util.threading import fetch_corresponding_thread
from tests.util.base import add_fake_thread, add_fake_message, generic_account

NAMESPACE_ID = 1
ACCOUNT_ID = 1

MockRawMessage = namedtuple('RawMessage', ['flags'])


@pytest.fixture
def folder_sync_engine(db, monkeypatch):
    # super ugly, but I don't want to have to mock tons of stuff
    import inbox.mailsync.backends.imap.generic
    from inbox.mailsync.backends.imap.generic import FolderSyncEngine
    monkeypatch.setattr(inbox.mailsync.backends.imap.generic,
                        "_pool", lambda(account): True)
    # setup a dummy FolderSyncEngine - we only need to call a couple
    # methods.
    email = "inboxapptest1@fastmail.fm"
    account = GenericAuthHandler('fastmail').create_account(
        db.session, email, {"email": email, "password": "BLAH"})
    db.session.add(account)
    db.session.commit()

    engine = None
    engine = FolderSyncEngine(account.id, "Inbox", 0,
                              email, "fastmail",
                              3200, None, 20, [])
    return engine


def test_generic_grouping(db, generic_account):
    thread = add_fake_thread(db.session, NAMESPACE_ID)
    message = add_fake_message(db.session, NAMESPACE_ID, thread,
                               subject="Golden Gate Park next Sat")
    ImapUid(message=message, account_id=ACCOUNT_ID,
            msg_uid=2222)

    thread = add_fake_thread(db.session, generic_account.namespace.id)
    message = add_fake_message(db.session, NAMESPACE_ID + 1, thread,
                               subject="Golden Gate Park next Sat")

    thread = fetch_corresponding_thread(db.session,
                                        generic_account.namespace.id, message)
    assert thread is None, ("fetch_similar_threads should "
                            "heed namespace boundaries")


def test_threading_limit(db, folder_sync_engine, monkeypatch):
    """Test that custom threading doesn't produce arbitrarily long threads,
    which eventually break things."""
    from inbox.models import Message, Thread, Account
    # Shorten bound to make test faster
    MAX_THREAD_LENGTH = 10
    monkeypatch.setattr(
        'inbox.mailsync.backends.imap.generic.MAX_THREAD_LENGTH',
        MAX_THREAD_LENGTH)
    namespace_id = folder_sync_engine.namespace_id
    account = db.session.query(Account).get(folder_sync_engine.account_id)
    account.namespace.create_canonical_tags()

    account.inbox_folder = Folder(account=account,
                                  name='Inbox',
                                  canonical_name='inbox')
    folder = account.inbox_folder

    msg = MockRawMessage([])
    for i in range(3 * MAX_THREAD_LENGTH):
        m = Message()
        m.namespace_id = namespace_id
        m.received_date = datetime.datetime.utcnow()
        m.references = []
        m.size = 0
        m.body = ''
        m.from_addr = [("Karim Hamidou", "karim@nilas.com")]
        m.to_addr = [("Eben Freeman", "eben@nilas.com")]
        m.snippet = ''
        m.subject = 'unique subject'
        uid = ImapUid(message=m, account=account, msg_uid=2222 + i,
                      folder=folder)
        folder_sync_engine.add_message_attrs(db.session, uid, msg)
        db.session.add(m)
        db.session.commit()
    new_threads = db.session.query(Thread). \
        filter(Thread.subject == 'unique subject').all()
    assert len(new_threads) == 3
    assert all(len(thread.messages) == MAX_THREAD_LENGTH for thread in
               new_threads)


if __name__ == '__main__':
    pytest.main([__file__])
