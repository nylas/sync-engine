# test that we correctly exit a sync engine instance if the folder we are
# trying to sync comes back as deleted while syncing

import pytest
from sqlalchemy.exc import IntegrityError

from inbox.mailsync.backends.imap.monitor import ImapSyncMonitor
from inbox.mailsync.backends.imap.generic import FolderSyncEngine
from inbox.mailsync.backends.base import MailsyncDone
from inbox.auth.generic import GenericAuthHandler
from inbox.crispin import FolderMissingError

TEST_YAHOO_EMAIL = "inboxapptest1@yahoo.com"


@pytest.fixture
def yahoo_account(db):
    account = GenericAuthHandler('yahoo').create_account(
        db.session, TEST_YAHOO_EMAIL,
        {"email": TEST_YAHOO_EMAIL, "password": "BLAH"})
    db.session.add(account)
    db.session.commit()
    return account


def raise_folder_error(*args, **kwargs):
    raise FolderMissingError()


@pytest.fixture
def sync_engine_stub(db, yahoo_account, monkeypatch):
    # setup a dummy FolderSyncEngine which raises a FolderMissingError
    monkeypatch.setattr('inbox.mailsync.backends.imap.generic._pool',
                        lambda account: True)

    engine = FolderSyncEngine(yahoo_account.id, "Inbox", 0,
                              TEST_YAHOO_EMAIL, "yahoo",
                              3200, None, 20, [])

    return engine


def test_folder_engine_exits_if_folder_missing(sync_engine_stub):
    # if the folder does not exist in our database, _load_state will
    # encounter an IntegrityError as it tries to insert a child
    # ImapFolderSyncStatus against an invalid foreign key
    with pytest.raises(IntegrityError):
        sync_engine_stub._load_state()

    # and we should use this to signal that mailsync is done
    with pytest.raises(MailsyncDone):
        sync_engine_stub._run()

    # also check that we handle the crispin select_folder error appropriately
    # within the core True loop of _run()
    sync_engine_stub._load_state = lambda: True
    sync_engine_stub.state = 'poll'
    sync_engine_stub.poll_impl = raise_folder_error
    with pytest.raises(MailsyncDone):
        sync_engine_stub._run()


def test_folder_monitor_handles_mailsync_done(yahoo_account, monkeypatch):
    # test that the ImapFolderMonitor exits cleanly when MailsyncDone
    # is raised as part of the initial sync.
    monitor = ImapSyncMonitor(yahoo_account)

    # Override the folders from `prepare_sync` to simulate a folder which was
    # genuinely returned here but then immediately deleted. This triggers
    # MailsyncDone (see the previous test).
    folders = [('missing_folder', 0)]
    monitor.prepare_sync = lambda: folders
    # Try to start a sync engine for this folder. It should exit.
    monitor.start_new_folder_sync_engines(set())
    assert len(monitor.folder_monitors) == 0

    # Note: it currently looks like ImapFolderMonitor doesn't have a good
    # way of handling MailsyncDone raises during the poll stage.
