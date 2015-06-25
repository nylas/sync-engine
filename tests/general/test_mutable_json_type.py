""" Tests for our mutable JSON column type. """

from datetime import datetime


def test_mutable_json_type(db, config, default_account, folder):
    """
    Test that FolderSync._sync_status which is a mutable JSON column is
    updated as expected.

    """
    from inbox.models.backends.imap import ImapFolderSyncStatus

    sync_status = ImapFolderSyncStatus(
        account_id=default_account.id,
        folder=folder)
    db.session.add(sync_status)
    db.session.commit()

    original_metrics = sync_status.metrics

    metrics = dict(download_uid_count=10,
                   queue_checked_at=datetime.utcnow())
    sync_status.update_metrics(metrics)

    updated_metrics = sync_status.metrics

    metrics.update(original_metrics)
    assert updated_metrics != original_metrics and updated_metrics == metrics,\
        'metrics not updated correctly'

    # Reupdate status
    new_metrics = dict(delete_uid_count=50,
                       download_uid_count=100,
                       queue_checked_at=datetime.utcnow())
    sync_status.update_metrics(new_metrics)

    latest_metrics = sync_status.metrics

    metrics.update(new_metrics)
    assert latest_metrics == metrics, 'metrics not re-updated correctly'
