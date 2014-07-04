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
    from inbox.models.backends.imap import ImapFolderSyncStatus

    account = db.session.query(Account).get(ACCOUNT_ID)

    sync_status = db.session.query(ImapFolderSyncStatus).filter_by(
        account_id=ACCOUNT_ID, folder_id=account.inbox_folder_id).one()

    original_metrics = sync_status.metrics

    metrics = dict(current_download_queue_size=10,
                   queue_checked_at=datetime.utcnow())
    sync_status.update_metrics(metrics)

    updated_metrics = sync_status.metrics

    metrics.update(original_metrics)
    assert updated_metrics != original_metrics and updated_metrics == metrics,\
        'metrics not updated correctly'

    # Reupdate status
    new_metrics = dict(delete_uid_count=50,
                       current_download_queue_size=100,
                       queue_checked_at=datetime.utcnow())
    sync_status.update_metrics(new_metrics)

    latest_metrics = sync_status.metrics

    metrics.update(new_metrics)
    assert latest_metrics == metrics, 'metrics not re-updated correctly'
