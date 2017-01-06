# flake8: noqa: F401
# test that we correctly exit a sync engine instance if the folder we are
# trying to sync comes back as deleted while syncing

import pytest
from sqlalchemy.exc import IntegrityError

from inbox.mailsync.backends.imap.monitor import ImapSyncMonitor
from inbox.mailsync.backends.imap.generic import FolderSyncEngine
from inbox.mailsync.backends.base import MailsyncDone
from inbox.models import Folder
from inbox.auth.generic import GenericAuthHandler
from inbox.crispin import FolderMissingError

TEST_YAHOO_EMAIL = "inboxapptest1@yahoo.com"


@pytest.fixture
def yahoo_account(db):
    account = GenericAuthHandler('yahoo').create_account(
        TEST_YAHOO_EMAIL,
        {"email": TEST_YAHOO_EMAIL, "password": "BLAH"})
    db.session.add(account)
    db.session.commit()
    return account


def raise_folder_error(*args, **kwargs):
    raise FolderMissingError()


@pytest.fixture
def sync_engine_stub(db, yahoo_account):
    db.session.add(Folder(account=yahoo_account, name='Inbox'))
    db.session.commit()
    engine = FolderSyncEngine(yahoo_account.id, yahoo_account.namespace.id,
                              "Inbox", TEST_YAHOO_EMAIL, "yahoo", None)

    return engine


def test_folder_engine_exits_if_folder_missing(db, yahoo_account,
                                               sync_engine_stub):
    # if the folder does not exist in our database, _load_state will
    # encounter an IntegrityError as it tries to insert a child
    # ImapFolderSyncStatus against an invalid foreign key
    folder = db.session.query(Folder).filter_by(account=yahoo_account,
                                                name='Inbox').one()
    db.session.delete(folder)
    db.session.commit()
    with pytest.raises(IntegrityError):
        sync_engine_stub.update_folder_sync_status(lambda s: s)

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
