# test that T441 doesn't reappear, ever.
import datetime
import pytest
from collections import namedtuple
from inbox.auth.generic import GenericAuthHandler


MockMessage = namedtuple('Message', ['subject'])
MockFolder = namedtuple('Message', ['name', 'canonical_name'])
MockRawMessage = namedtuple('RawMessage', ['flags'])


class MockImapUID(object):
    def __init__(self, message, account):
        self.message = message
        self.account = account

    def update_imap_flags(self, *args, **kwargs):
        pass


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
                              3200, None, 20, None)
    return engine


def test_generic_foldersyncengine(db, folder_sync_engine):
    message = MockMessage("Golden Gate Park next Sat")
    imapuid = MockImapUID(message, None)
    messages = folder_sync_engine.fetch_similar_threads(db.session, imapuid)
    assert messages == [], ("fetch_similar_threads should "
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
    folder = MockFolder('inbox', 'inbox')
    msg = MockRawMessage(None)
    for _ in range(3 * MAX_THREAD_LENGTH):
        m = Message()
        m.namespace_id = namespace_id
        m.received_date = datetime.datetime.utcnow()
        m.references = []
        m.size = 0
        m.sanitized_body = ''
        m.snippet = ''
        m.subject = 'unique subject'
        uid = MockImapUID(m, account)
        folder_sync_engine.add_message_attrs(db.session, uid, msg, folder)
        db.session.add(m)
        db.session.commit()
    new_threads = db.session.query(Thread). \
        filter(Thread.subject == 'unique subject').all()
    assert len(new_threads) == 3
    assert all(len(thread.messages) == MAX_THREAD_LENGTH for thread in
               new_threads)


if __name__ == '__main__':
    pytest.main([__file__])
