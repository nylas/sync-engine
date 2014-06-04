import pytest

from tests.util.base import action_queue

# Note that we're only testing GMAIL local actions right now, this account
# MUST be a Gmail account.
ACCOUNT_ID = 1


class TestLocalClientActions(object):
    """ Makes sure events are created properly (doesn't test action processing)
        and that the local datastore looks good.
    """
    @pytest.fixture(autouse=True)
    def register_action_backends(db):
        """Normally action backends only get registered when the actions
        rqworker starts. So we need to register them explicitly for these
        tests."""
        from inbox.server.actions.base import register_backends
        register_backends()

    def test_local_archive(self, db, action_queue):
        from inbox.server.models.tables.base import Account, FolderItem
        from inbox.server.actions.base import archive

        account = db.session.query(Account).get(ACCOUNT_ID)

        archive(db.session, ACCOUNT_ID, 1)

        inbox_items = db.session.query(FolderItem).filter(
            FolderItem.thread_id == 1,
            FolderItem.folder_id == account.inbox_folder_id).count()
        assert inbox_items == 0, "inbox entry still present"

        archive_items = db.session.query(FolderItem).filter(
            FolderItem.thread_id == 1,
            FolderItem.folder_id == account.all_folder_id).count()
        assert archive_items == 1, "all entry missing"

        assert action_queue.count == 1, "sync-back event not queued"

    def test_set_local_unread(self, db, action_queue):
        from inbox.server.models.tables.base import Account, Thread
        from inbox.server.actions.base import set_unread
        thread = db.session.query(Thread).filter_by(id=1).one()
        account = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()

        set_unread(db.session, account, thread, True)
        assert not any(message.is_read for message in thread.messages)

        set_unread(db.session, account, thread, False)
        assert all(message.is_read for message in thread.messages)

    def test_local_move(self, db, action_queue):
        from inbox.server.models.tables.base import Account, FolderItem, Folder
        from inbox.server.actions.base import move

        account = db.session.query(Account).get(ACCOUNT_ID)

        move(db.session, ACCOUNT_ID, 1, account.inbox_folder.name, 'testlabel')

        inbox_items = db.session.query(FolderItem).filter(
            FolderItem.thread_id == 1,
            FolderItem.folder_id == account.inbox_folder_id).count()
        assert inbox_items == 0, "inbox entry still present"

        testlabel_items = db.session.query(FolderItem).join(Folder).filter(
            FolderItem.thread_id == 1,
            Folder.name == 'testlabel').count()
        assert testlabel_items == 1, "testlabel entry not present"

        assert action_queue.count == 1, "sync-back event not queued"

    def test_local_copy(self, db, action_queue):
        from inbox.server.models.tables.base import Account, FolderItem, Folder
        from inbox.server.actions.base import copy

        account = db.session.query(Account).get(ACCOUNT_ID)

        copy(db.session, ACCOUNT_ID, 1, account.inbox_folder.name, 'testlabel')

        inbox_items = db.session.query(FolderItem).filter(
            FolderItem.thread_id == 1,
            FolderItem.folder_id == account.inbox_folder_id).count()
        assert inbox_items == 1, "inbox entry missing"

        testlabel_items = db.session.query(FolderItem).join(Folder).filter(
            FolderItem.thread_id == 1,
            Folder.name == 'testlabel').count()
        assert testlabel_items == 1, "testlabel entry missing"

        assert action_queue.count == 1, "sync-back event not queued"

    def test_local_delete(self, db, action_queue):
        from inbox.server.models.tables.base import Account, FolderItem
        from inbox.server.actions.base import delete

        account = db.session.query(Account).get(ACCOUNT_ID)

        delete(db.session, ACCOUNT_ID, 1, account.inbox_folder.name)

        inbox_items = db.session.query(FolderItem).filter(
            FolderItem.thread_id == 1,
            FolderItem.folder_id == account.inbox_folder_id).count()
        assert inbox_items == 0, "inbox entry still there"

        archive_items = db.session.query(FolderItem).filter(
            FolderItem.thread_id == 1,
            FolderItem.folder_id == account.all_folder_id).count()
        assert archive_items == 1, "all entry missing"

        assert action_queue.count == 1, "sync-back event not queued"

        delete(db.session, ACCOUNT_ID, 1, account.all_folder.name)

        inbox_items = db.session.query(FolderItem).filter(
            FolderItem.thread_id == 1,
            FolderItem.folder_id == account.inbox_folder_id).count()
        assert inbox_items == 0, "inbox entry still there"

        archive_items = db.session.query(FolderItem).filter(
            FolderItem.thread_id == 1,
            FolderItem.folder_id == account.all_folder_id).count()
        assert archive_items == 0, "archive entry still there"

        assert action_queue.count == 2, "sync-back event not queued"

        # TODO: test that message data is purged from the database (this
        # involves another worker, so maybe the test doesn't belong here in
        # particular)
