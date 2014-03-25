import json

import pytest

from .util.api import api_client
from .util.base import action_queue

USER_ID = 1
NAMESPACE_ID = 1



class TestLocalClientActions(object):
    """ Makes sure events are created properly (doesn't test action processing)
        and that the local datastore looks good.
    """
    @pytest.fixture(autouse=True)
    def register_action_backends(db):
        """Normally action backends only get registered when the actions
        rqworker starts. So we need to register them explicitly for these
        tests."""
        from inbox.server.actions import register_backends
        register_backends()

    def test_local_archive(self, db, api_client, action_queue):
        from inbox.server.models.tables.base import FolderItem

        result = api_client.archive(USER_ID, NAMESPACE_ID, 1)
        assert result == json.dumps("OK"), "archive API call failed"

        inbox_items = db.session.query(FolderItem).filter_by(
                thread_id=1, folder_name='inbox').count()
        assert inbox_items == 0, "inbox entry still present"

        archive_items = db.session.query(FolderItem).filter_by(
                thread_id=1, folder_name='archive').count()
        assert archive_items == 1, "archive entry missing"

        assert action_queue.count == 1, "sync-back event not queued"

    def test_local_move(self, db, api_client, action_queue):
        from inbox.server.models.tables.base import FolderItem

        result = api_client.move(USER_ID, NAMESPACE_ID, 1, 'inbox',
                'testlabel')
        assert result == json.dumps("OK"), "move API call failed"

        inbox_items = db.session.query(FolderItem).filter_by(
                thread_id=1, folder_name='inbox').count()
        assert inbox_items == 0, "inbox entry still present"

        testlabel_items = db.session.query(FolderItem).filter_by(
                thread_id=1, folder_name='testlabel').count()
        assert testlabel_items == 1, "testlabel entry not present"

        assert action_queue.count == 1, "sync-back event not queued"

    def test_local_copy(self, db, api_client, action_queue):
        from inbox.server.models.tables.base import FolderItem

        result = api_client.copy(USER_ID, NAMESPACE_ID, 1, 'inbox',
                'testlabel')
        assert result == json.dumps("OK"), "copy API call failed"

        inbox_items = db.session.query(FolderItem).filter_by(
                thread_id=1, folder_name='inbox').count()
        assert inbox_items == 1, "inbox entry missing"

        testlabel_items = db.session.query(FolderItem).filter_by(
                thread_id=1, folder_name='testlabel').count()
        assert testlabel_items == 1, "testlabel entry missing"

        assert action_queue.count == 1, "sync-back event not queued"

    def test_local_delete(self, db, api_client, action_queue):
        from inbox.server.models.tables.base import FolderItem

        result = api_client.delete(USER_ID, NAMESPACE_ID, 1, 'inbox')
        assert result == json.dumps("OK"), "delete API call failed"

        inbox_items = db.session.query(FolderItem).filter_by(
                thread_id=1, folder_name='inbox').count()
        assert inbox_items == 0, "inbox entry still there"

        archive_items = db.session.query(FolderItem).filter_by(
                thread_id=1, folder_name='archive').count()
        assert archive_items == 1, "archive entry missing"

        assert action_queue.count == 1, "sync-back event not queued"

        result = api_client.delete(USER_ID, NAMESPACE_ID, 1, 'archive')
        assert result == json.dumps("OK"), "delete API call failed"

        inbox_items = db.session.query(FolderItem).filter_by(
                thread_id=1, folder_name='inbox').count()
        assert inbox_items == 0, "inbox entry still there"

        # I don't understand why we need to refresh the session here, but
        # if we don't we get stale data. :/
        db.new_session()
        archive_items = db.session.query(FolderItem).filter_by(
                thread_id=1, folder_name='archive').count()
        assert archive_items == 0, "archive entry still there"

        assert action_queue.count == 2, "sync-back event not queued"

        # TODO: test that message data is purged from the database (this involves
        # another worker, so maybe the test doesn't belong here in particular)
