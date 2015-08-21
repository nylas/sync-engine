from inbox.crispin import RawFolder
from inbox.mailsync.backends.imap.monitor import ImapSyncMonitor
from inbox.mailsync.backends.gmail import GmailSyncMonitor
from inbox.models import Folder, Label, Category


def test_imap_save_generic_folder_names(db, default_account):
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


def test_imap_handle_folder_renames(db, default_account):
    monitor = ImapSyncMonitor(default_account)
    folder_names_and_roles = {
        ('INBOX', 'inbox'),
        ('[Gmail]/Todos', 'all'),
        ('[Gmail]/Basura', 'trash')
    }

    folders_renamed = {
        ('INBOX', 'inbox'),
        ('[Gmail]/All', 'all'),
        ('[Gmail]/Trash', 'trash')
    }
    original_raw_folders = [RawFolder(*args) for args in
                            folder_names_and_roles]
    renamed_raw_folders = [RawFolder(*args) for args in folders_renamed]
    monitor.save_folder_names(db.session, original_raw_folders)
    assert len(db.session.query(Folder).filter(
        Folder.account_id == default_account.id).all()) == 3

    monitor.save_folder_names(db.session, renamed_raw_folders)
    saved_folder_data = set(
        db.session.query(Folder.name, Folder.canonical_name).filter(
            Folder.account_id == default_account.id).all())
    assert saved_folder_data == folders_renamed


def test_gmail_handle_folder_renames(db, default_account):
    monitor = GmailSyncMonitor(default_account)
    folder_names_and_roles = {
        ('[Gmail]/Todos', 'all'),
        ('[Gmail]/Basura', 'trash')
    }

    folders_renamed = {
        ('[Gmail]/All', 'all'),
        ('[Gmail]/Trash', 'trash')
    }
    original_raw_folders = [RawFolder(*args) for args in
                            folder_names_and_roles]
    renamed_raw_folders = [RawFolder(*args) for args in folders_renamed]
    monitor.save_folder_names(db.session, original_raw_folders)
    original_folders = db.session.query(Folder).filter(
        Folder.account_id == default_account.id).all()

    assert len(original_folders) == 2
    for folder in original_folders:
        assert folder.category != None

    original_categories = {f.canonical_name: f.category.display_name for f in
                            original_folders}

    for folder in folder_names_and_roles:
        display_name, role = folder
        assert original_categories[role] == display_name

    monitor.save_folder_names(db.session, renamed_raw_folders)
    saved_folder_data = set(
        db.session.query(Folder.name, Folder.canonical_name).filter(
            Folder.account_id == default_account.id).all())
    assert saved_folder_data == folders_renamed

    renamed_folders = db.session.query(Folder).filter(
        Folder.account_id == default_account.id).all()

    for folder in renamed_folders:
        assert folder.category != None

    renamed_categories = {f.canonical_name: f.category.display_name for f in
                            renamed_folders}

    for folder in folders_renamed:
        display_name, role = folder
        assert renamed_categories[role] == display_name


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
