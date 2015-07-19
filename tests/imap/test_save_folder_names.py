from inbox.crispin import RawFolder
from inbox.mailsync.backends.imap.monitor import ImapSyncMonitor
from inbox.mailsync.backends.gmail import GmailSyncMonitor
from inbox.models import Folder, Label, Category
from inbox.models.backends.imap import ImapFolderSyncStatus, ImapFolderInfo


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


def test_save_generic_folder_names(db, default_account):
    monitor = ImapSyncMonitor(default_account)
    folder_names_and_roles = {
        ('INBOX', 'inbox'),
        ('Sent Mail', 'sent'),
        ('Sent Messages', 'sent'),
        ('Drafts', 'drafts'),
        ('Miscellania', None),
        ('miscellania', None),
        ('Recipes', None),
    }
    raw_folders = [RawFolder(*args) for args in folder_names_and_roles]
    monitor.save_folder_names(db.session, raw_folders)
    saved_folder_data = set(
        db.session.query(Folder.name, Folder.canonical_name).filter(
            Folder.account_id == default_account.id).all())
    assert saved_folder_data == folder_names_and_roles


def test_handle_folder_deletions(db, default_account):
    monitor = ImapSyncMonitor(default_account)
    folder_names_and_roles = {
        ('INBOX', 'inbox'),
        ('Miscellania', None),
    }
    raw_folders = [RawFolder(*args) for args in folder_names_and_roles]
    monitor.save_folder_names(db.session, raw_folders)
    assert len(db.session.query(Folder).filter(
        Folder.account_id == default_account.id).all()) == 2

    monitor.save_folder_names(db.session, [RawFolder('INBOX', 'inbox')])
    saved_folder_data = set(
        db.session.query(Folder.name, Folder.canonical_name).filter(
            Folder.account_id == default_account.id).all())
    assert saved_folder_data == {('INBOX', 'inbox')}


def test_save_gmail_folder_names(db, default_account):
    monitor = GmailSyncMonitor(default_account)
    folder_names_and_roles = {
        ('Inbox', 'inbox'),
        ('[Gmail]/All Mail', 'all'),
        ('[Gmail]/Trash', 'trash'),
        ('[Gmail]/Spam', 'spam'),
        ('Miscellania', None),
        ('Recipes', None),
    }
    raw_folders = [RawFolder(*args) for args in folder_names_and_roles]
    monitor.save_folder_names(db.session, raw_folders)

    saved_folder_data = set(
        db.session.query(Folder.name, Folder.canonical_name).filter(
            Folder.account_id == default_account.id)
    )
    assert saved_folder_data == {
        ('[Gmail]/All Mail', 'all'),
        ('[Gmail]/Trash', 'trash'),
        ('[Gmail]/Spam', 'spam')
    }

    # Casing on "Inbox" is different to make what we get from folder listing
    # consistent with what we get in X-GM-LABELS during sync.
    expected_saved_names_and_roles = {
        ('Inbox', 'inbox'),
        ('[Gmail]/All Mail', 'all'),
        ('[Gmail]/Trash', 'trash'),
        ('[Gmail]/Spam', 'spam'),
        ('Miscellania', None),
        ('Recipes', None),
    }

    saved_label_data = set(
        db.session.query(Label.name, Label.canonical_name).filter(
            Label.account_id == default_account.id)
    )
    saved_category_data = set(
        db.session.query(Category.display_name, Category.name).filter(
            Category.namespace_id == default_account.namespace.id)
    )
    assert saved_label_data == expected_saved_names_and_roles
    assert saved_category_data == expected_saved_names_and_roles


def test_handle_trailing_whitespace(db, default_account):
    raw_folders = [
        RawFolder('Miscellania', None),
        RawFolder('Miscellania  ', None),
        RawFolder('Inbox', 'inbox')
    ]
    monitor = ImapSyncMonitor(default_account)
    monitor.save_folder_names(db.session, raw_folders)
    saved_folder_data = set(
        db.session.query(Folder.name, Folder.canonical_name).filter(
            Folder.account_id == default_account.id)
    )
    assert saved_folder_data == {('Miscellania', None), ('Inbox', 'inbox')}
