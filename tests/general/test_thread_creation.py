# test that T441 doesn't reappear, ever.
import datetime
import pytest
from collections import namedtuple
from inbox.auth.generic import GenericAuthHandler
from inbox.models import Folder, Namespace
from inbox.models.backends.imap import ImapUid
from inbox.util.threading import fetch_corresponding_thread
from tests.util.base import add_fake_thread, add_fake_message

MockRawMessage = namedtuple('RawMessage', ['flags'])


@pytest.fixture
def folder_sync_engine(db):
    from inbox.mailsync.backends.imap.generic import FolderSyncEngine
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
                              None)
    return engine


def test_generic_grouping(db, default_account):
    thread = add_fake_thread(db.session, default_account.namespace.id)
    message = add_fake_message(db.session, default_account.namespace.id,
                               thread, subject="Golden Gate Park next Sat")
    folder = Folder(account=default_account, name='Inbox',
                    canonical_name='inbox')
    ImapUid(message=message, account_id=default_account.id,
            msg_uid=2222, folder=folder)

    thread = add_fake_thread(db.session, default_account.namespace.id)

    new_namespace = Namespace()
    db.session.add(new_namespace)
    db.session.commit()
    message = add_fake_message(db.session, new_namespace.id,
                               thread, subject="Golden Gate Park next Sat")

    thread = fetch_corresponding_thread(db.session,
                                        default_account.namespace.id, message)
    assert thread is None, ("fetch_similar_threads should "
                            "heed namespace boundaries")


def test_threading_limit(db, folder_sync_engine, monkeypatch):
    """Test that custom threading doesn't produce arbitrarily long threads,
    which eventually break things."""
    from inbox.models import Message, Thread
    # Shorten bound to make test faster
    MAX_THREAD_LENGTH = 10
    monkeypatch.setattr(
        'inbox.mailsync.backends.imap.generic.MAX_THREAD_LENGTH',
        MAX_THREAD_LENGTH)
    namespace_id = folder_sync_engine.namespace_id

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
        db.session.add(m)
        folder_sync_engine.add_message_to_thread(db.session, m, msg)
        db.session.commit()
    new_threads = db.session.query(Thread). \
        filter(Thread.subject == 'unique subject').all()
    assert len(new_threads) == 3
    assert all(len(thread.messages) == MAX_THREAD_LENGTH for thread in
               new_threads)


if __name__ == '__main__':
    pytest.main([__file__])
