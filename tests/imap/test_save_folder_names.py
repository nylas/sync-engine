import pytest
from inbox.mailsync.backends.base import (save_folder_names,
                                          mailsync_session_scope)
from inbox.models import Folder, Tag
from inbox.models.backends.imap import ImapFolderSyncStatus, ImapFolderInfo
from inbox.log import get_logger

ACCOUNT_ID = 1


@pytest.fixture
def folder_name_mapping():
    return {
        'inbox': 'Inbox',
        'spam': '[Gmail]/Spam',
        'all': '[Gmail]/All Mail',
        'sent': '[Gmail]/Sent Mail',
        'drafts': '[Gmail]/Drafts',
        'extra': ['Jobslist', 'Random']
    }


def add_imap_status_info_rows(folder_id, account_id, db_session):
    """Add placeholder ImapFolderSyncStatus and ImapFolderInfo rows for this
       folder_id if none exist.
    """
    if not db_session.query(ImapFolderSyncStatus).filter_by(
            account_id=account_id, folder_id=folder_id).all():
        db_session.add(ImapFolderSyncStatus(
            account_id=ACCOUNT_ID,
            folder_id=folder_id,
            state='initial'))

    if not db_session.query(ImapFolderInfo).filter_by(
            account_id=account_id, folder_id=folder_id).all():
        db_session.add(ImapFolderInfo(
            account_id=account_id,
            folder_id=folder_id,
            uidvalidity=1,
            highestmodseq=22))


def test_save_folder_names(db, folder_name_mapping):
    with mailsync_session_scope() as db_session:
        log = get_logger()
        save_folder_names(log, ACCOUNT_ID, folder_name_mapping, db_session)
        saved_folder_names = {name for name, in
                              db_session.query(Folder.name).filter(
                                  Folder.account_id == ACCOUNT_ID)}
        assert saved_folder_names == {'Inbox', '[Gmail]/Spam',
                                      '[Gmail]/All Mail', '[Gmail]/Sent Mail',
                                      '[Gmail]/Drafts', 'Jobslist', 'Random'}


def test_sync_folder_deletes(db, folder_name_mapping):
    """Test that folder deletions properly cascade to deletions of
       ImapFolderSyncStatus and ImapFolderInfo.
    """
    with mailsync_session_scope() as db_session:
        log = get_logger()
        save_folder_names(log, ACCOUNT_ID, folder_name_mapping, db_session)
        folders = db_session.query(Folder).filter_by(account_id=ACCOUNT_ID)
        for folder in folders:
            add_imap_status_info_rows(folder.id, ACCOUNT_ID, db_session)
        db_session.commit()
        assert db_session.query(ImapFolderInfo).count() == 7
        assert db_session.query(ImapFolderSyncStatus).count() == 7

        folder_name_mapping['extra'] = ['Jobslist']
        save_folder_names(log, ACCOUNT_ID, folder_name_mapping, db_session)
        saved_folder_names = {name for name, in
                              db_session.query(Folder.name).filter(
                                  Folder.account_id == ACCOUNT_ID)}
        assert saved_folder_names == {'Inbox', '[Gmail]/Spam',
                                      '[Gmail]/All Mail', '[Gmail]/Sent Mail',
                                      '[Gmail]/Drafts', 'Jobslist'}
        assert db_session.query(ImapFolderInfo).count() == 6
        assert db_session.query(ImapFolderSyncStatus).count() == 6


def test_folder_delete_cascades_to_tag(db, folder_name_mapping):
    """Test that when a tag (folder) is deleted, we properly cascade to delete
       the Tag object too.
    """
    with mailsync_session_scope() as db_session:
        log = get_logger()
        save_folder_names(log, ACCOUNT_ID, folder_name_mapping, db_session)
        folders = db_session.query(Folder).filter_by(account_id=ACCOUNT_ID)
        assert folders.count() == 7
        random_folder = folders.filter_by(name='Random').first()
        assert random_folder is not None
        random_tag = random_folder.get_associated_tag(db_session)
        random_tag_id = random_tag.id
        db.session.commit()

        folder_name_mapping['extra'] = ['Jobslist']
        save_folder_names(log, ACCOUNT_ID, folder_name_mapping, db_session)
        db.session.commit()
        random_tag = db_session.query(Tag).get(random_tag_id)
        assert random_tag is None
