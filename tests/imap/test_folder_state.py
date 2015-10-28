from inbox.crispin import RawFolder
from inbox.models import Folder
from inbox.mailsync.backends.imap.monitor import ImapSyncMonitor
from inbox.models.backends.imap import ImapFolderInfo, ImapFolderSyncStatus


def add_imap_status_info_rows(folder_id, account_id, db_session):
    """Add placeholder ImapFolderSyncStatus and ImapFolderInfo rows for this
       folder_id if none exist.
    """
    if not db_session.query(ImapFolderSyncStatus).filter_by(
            account_id=account_id, folder_id=folder_id).all():
        db_session.add(ImapFolderSyncStatus(
            account_id=account_id,
            folder_id=folder_id,
            state='initial'))

    if not db_session.query(ImapFolderInfo).filter_by(
            account_id=account_id, folder_id=folder_id).all():
        db_session.add(ImapFolderInfo(
            account_id=account_id,
            folder_id=folder_id,
            uidvalidity=1,
            highestmodseq=22))


def create_foldersyncstatuses(db, default_account):
    # Create a bunch of folder sync statuses.
    monitor = ImapSyncMonitor(default_account)

    folder_names_and_roles = {
        RawFolder('INBOX', 'inbox'),
        RawFolder('Sent Mail', 'sent'),
        RawFolder('Sent Messages', 'sent'),
        RawFolder('Drafts', 'drafts'),
        RawFolder('Miscellania', None),
        RawFolder('miscellania', None),
        RawFolder('Recipes', None),
    }
    monitor.save_folder_names(db.session, folder_names_and_roles)
    folders = db.session.query(Folder).filter_by(account_id=default_account.id)
    for folder in folders:
        add_imap_status_info_rows(folder.id, default_account.id, db.session)
    db.session.commit()


def test_imap_folder_run_state_always_true(db, default_account):
    """Test that for an IMAP account, the sync_should_run flag on the
       account's folder statuses is always true. (This is not the case for
       all backends, and may not always be the case in future. Other backends
       should have an appropriate test parallel to this one.)

       The sync_should_run flag for a folder reflects whether that folder's
       sync should be running iff the account's sync should be running, so
       overall state depends on the account.sync_should_run bit being correct.
    """
    create_foldersyncstatuses(db, default_account)

    for folderstatus in default_account.foldersyncstatuses:
        assert folderstatus.sync_should_run is True


def test_imap_folder_sync_enabled(db, default_account):
    """Test that the IMAP folder's sync_enabled property mirrors the account
       level sync_enabled property. (Again, this might not be the case for non-
       IMAP backends.)
    """
    create_foldersyncstatuses(db, default_account)

    assert all([fs.sync_enabled for fs in default_account.foldersyncstatuses])

    # Disable sync. Folders should now not have sync_enabled.
    default_account.disable_sync('testing')
    db.session.commit()

    assert all([not fs.sync_enabled
                for fs in default_account.foldersyncstatuses])
