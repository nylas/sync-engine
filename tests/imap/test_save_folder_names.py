import pytest
import gevent
from gevent.pool import Group


from inbox.mailsync.backends.base import (save_folder_names,
                                          mailsync_session_scope)
from inbox.models import Folder, Tag, Account
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


def test_name_collision_folders(db, folder_name_mapping):
    # test that when a user-created folder called 'spam' is created, we don't
    # associate it with the canonical spam tag, but instead give it its own
    # tag

    folder_name_mapping['extra'] = ['spam']

    with mailsync_session_scope() as db_session:
        log = get_logger()
        save_folder_names(log, ACCOUNT_ID, folder_name_mapping, db_session)
        account = db_session.query(Account).get(ACCOUNT_ID)
        spam_tags = db_session.query(Tag).filter_by(
            namespace_id=account.namespace.id,
            name='spam')
        # There should be one 'Gmail/Spam' canonical tag
        assert spam_tags.count() == 1
        assert spam_tags.first().public_id == 'spam'
        # and one 'imap/spam' non-canonical tag with public_id != 'spam'
        spam_tags = db_session.query(Tag).filter_by(
            namespace_id=account.namespace.id,
            name='imap/spam')
        assert spam_tags.count() == 1
        assert spam_tags.first().public_id != 'spam'

    # test that when a folder called 'spam' is deleted, we don't delete
    # the canonical 'spam' tag
    folder_name_mapping['extra'] = []
    with mailsync_session_scope() as db_session:
        log = get_logger()
        save_folder_names(log, ACCOUNT_ID, folder_name_mapping, db_session)
        account = db_session.query(Account).get(ACCOUNT_ID)
        spam_tags = db_session.query(Tag).filter_by(
            namespace_id=account.namespace.id,
            name='spam')
        # The 'Gmail/Spam' canonical tag should still remain.
        assert spam_tags.count() == 1
        assert spam_tags.first().public_id == 'spam'
        # The 'imap/spam' non-canonical tag shouldn't
        spam_tags = db_session.query(Tag).filter_by(
            namespace_id=account.namespace.id,
            name='imap/spam')
        assert spam_tags.count() == 0


def test_parallel_folder_syncs(db, folder_name_mapping, monkeypatch):
    # test that when we run save_folder_names in parallel, we only create one
    # tag for that folder. this happens when the CondstoreFolderSyncEngine
    # checks for UID changes.

    # patching the heartbeat clear means that we force the first greenlet to
    # wait around (there is a deleted folder in folder_name_mapping), thereby
    # assuring that the second greenlet will overtake it and force any
    # potential race condition around tag creation.
    def clear_heartbeat_patch(w, x, y, z):
        gevent.sleep(1)

    monkeypatch.setattr('inbox.heartbeat.store.HeartbeatStore.remove_folders',
                        clear_heartbeat_patch)

    log = get_logger()
    group = Group()
    with mailsync_session_scope() as db_session:
        group.spawn(save_folder_names, log, ACCOUNT_ID,
                    folder_name_mapping, db_session)
    with mailsync_session_scope() as db_session:
        group.spawn(save_folder_names, log, ACCOUNT_ID,
                    folder_name_mapping, db_session)
    group.join()

    with mailsync_session_scope() as db_session:
        account = db_session.query(Account).get(ACCOUNT_ID)
        random_tags = db_session.query(Tag).filter_by(
            namespace_id=account.namespace.id,
            name='random')
        assert random_tags.count() == 1
