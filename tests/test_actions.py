import json

from .util.api import api_client
from .util.base import action_queue

USER_ID = 1
NAMESPACE_ID = 1

# Unit tests for local client actions. Makes sure events are created properly
# (doesn't test action processing) and the local datastore looks good.

def test_local_archive(db, api_client, action_queue):
    from inbox.server.models.tables import FolderItem

    result = api_client.archive(USER_ID, NAMESPACE_ID, 1)
    assert result == json.dumps("OK"), "archive API call failed"

    inbox_items = db.session.query(FolderItem).filter_by(
            thread_id=1, folder_name='inbox').count()
    assert inbox_items == 0, "inbox entry still present"

    archive_items = db.session.query(FolderItem).filter_by(
            thread_id=1, folder_name='archive').count()
    assert archive_items == 1, "archive entry missing"

    assert action_queue.count == 1, "sync-back event not queued"

def test_local_move(db, api_client, action_queue):
    from inbox.server.models.tables import FolderItem

    result = api_client.move(USER_ID, NAMESPACE_ID, 1, 'archive',
            'inbox')
    assert result == json.dumps("OK"), "move API call failed"

    # not sure why we need to refresh the session here, but we do otherwise
    # we get stale data :/
    db.new_session()
    inbox_items = db.session.query(FolderItem).filter_by(
            thread_id=1, folder_name='inbox').count()
    assert inbox_items == 1, "inbox entry missing"

    archive_items = db.session.query(FolderItem).filter_by(
            thread_id=1, folder_name='archive').count()
    assert archive_items == 0, "archive entry still present"

    assert action_queue.count == 1, "sync-back event not queued"

def test_local_copy(db, api_client, action_queue):
    from inbox.server.models.tables import FolderItem

    result = api_client.copy(USER_ID, NAMESPACE_ID, 1, 'inbox',
            'archive')
    assert result == json.dumps("OK"), "copy API call failed"

    # not sure why we need to refresh the session here, but we do otherwise
    # we get stale data :/
    db.new_session()
    inbox_items = db.session.query(FolderItem).filter_by(
            thread_id=1, folder_name='inbox').count()
    assert inbox_items == 1, "inbox entry missing"

    archive_items = db.session.query(FolderItem).filter_by(
            thread_id=1, folder_name='archive').count()
    assert archive_items == 1, "archive entry missing"

    assert action_queue.count == 1, "sync-back event not queued"

def test_local_delete(db, api_client, action_queue):
    from inbox.server.models.tables import FolderItem

    result = api_client.delete(USER_ID, NAMESPACE_ID, 1, 'inbox')
    assert result == json.dumps("OK"), "delete API call failed"

    # not sure why we need to refresh the session here, but we do otherwise
    # we get stale data :/
    db.new_session()
    inbox_items = db.session.query(FolderItem).filter_by(
            thread_id=1, folder_name='inbox').count()
    assert inbox_items == 0, "inbox entry still there"

    archive_items = db.session.query(FolderItem).filter_by(
            thread_id=1, folder_name='archive').count()
    assert archive_items == 1, "archive entry missing"

    assert action_queue.count == 1, "sync-back event not queued"

    result = api_client.delete(USER_ID, NAMESPACE_ID, 1, 'archive')
    assert result == json.dumps("OK"), "delete API call failed"

    # not sure why we need to refresh the session here, but we do otherwise
    # we get stale data :/
    db.new_session()
    inbox_items = db.session.query(FolderItem).filter_by(
            thread_id=1, folder_name='inbox').count()
    assert inbox_items == 0, "inbox entry still there"

    archive_items = db.session.query(FolderItem).filter_by(
            thread_id=1, folder_name='archive').count()
    assert archive_items == 0, "archive entry still there"

    assert action_queue.count == 2, "sync-back event not queued"

    # TODO: test that message data is purged from the database (this involves
    # another worker, so maybe the test doesn't belong here in particular)
