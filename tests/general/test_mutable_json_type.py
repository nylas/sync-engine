""" Tests for our mutable JSON column type. """

from datetime import datetime

ACCOUNT_ID = 1


def test_mutable_json_type(db, config):
    """
    Test that FolderSync._sync_status which is a mutable JSON column is
    updated as expected.

    """
    from inbox.models import register_backends
    register_backends()
    from inbox.models.account import Account
    from inbox.models.backends.imap import FolderSync

    account = db.session.query(Account).get(ACCOUNT_ID)

    foldersync = db.session.query(FolderSync).filter(
        FolderSync.account_id == ACCOUNT_ID,
        FolderSync.folder_name == account.inbox_folder.name).one()

    original_status = foldersync.sync_status

    metrics = dict(current_download_queue_size=10,
                   queue_checked_at=datetime.utcnow())

    foldersync.update_sync_status(metrics)

    updated_status = foldersync.sync_status

    assert updated_status != original_status and updated_status == metrics, \
        'sync_status not updated correctly'

    new_metrics = dict(delete_uid_count=50,
                       current_download_queue_size=100,
                       queue_checked_at=datetime.utcnow())

    foldersync.update_sync_status(new_metrics)

    latest_status = foldersync.sync_status

    metrics.update(new_metrics)

    assert latest_status == metrics, 'sync_status not re-updated correctly'
