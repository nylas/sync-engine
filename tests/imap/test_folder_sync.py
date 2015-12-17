import pytest
from hashlib import sha256
from gevent.lock import BoundedSemaphore
from inbox.models import Folder, Message
from inbox.models.backends.imap import (ImapFolderSyncStatus, ImapUid,
                                        ImapFolderInfo)
from inbox.mailsync.backends.imap.generic import FolderSyncEngine
from inbox.mailsync.backends.gmail import GmailFolderSyncEngine
from inbox.mailsync.exc import UidInvalid
from tests.imap.data import uids, uid_data, mock_imapclient  # noqa


def create_folder_with_syncstatus(account, name, canonical_name,
                                  db_session):
    folder = Folder.find_or_create(db_session, account, name, canonical_name)
    folder.imapsyncstatus = ImapFolderSyncStatus(account=account)
    db_session.commit()
    return folder


@pytest.fixture
def inbox_folder(db, generic_account):
    return create_folder_with_syncstatus(generic_account, 'Inbox', 'inbox',
                                         db.session)


@pytest.fixture
def all_mail_folder(db, default_account):
    return create_folder_with_syncstatus(default_account, '[Gmail]/All Mail',
                                         'all', db.session)


@pytest.fixture
def trash_folder(db, default_account):
    return create_folder_with_syncstatus(default_account, '[Gmail]/Trash',
                                         'trash', db.session)


def test_initial_sync(db, generic_account, inbox_folder, mock_imapclient):
    # We should really be using hypothesis.given() to generate lots of
    # different uid sets, but it's not trivial to ensure that no state is
    # carried over between runs. This will have to suffice for now as a way to
    # at least establish coverage.
    uid_dict = uids.example()
    mock_imapclient.add_folder_data(inbox_folder.name, uid_dict)

    folder_sync_engine = FolderSyncEngine(generic_account.id,
                                          generic_account.namespace.id,
                                          inbox_folder.name,
                                          inbox_folder.id,
                                          generic_account.email_address,
                                          'custom',
                                          BoundedSemaphore(1))
    folder_sync_engine.initial_sync()

    saved_uids = db.session.query(ImapUid).filter(
        ImapUid.folder_id == inbox_folder.id)
    assert {u.msg_uid for u in saved_uids} == set(uid_dict)

    saved_message_hashes = {u.message.data_sha256 for u in saved_uids}
    assert saved_message_hashes == {sha256(v['BODY[]']).hexdigest() for v in
                                    uid_dict.values()}


def test_new_uids_synced_when_polling(db, generic_account, inbox_folder,
                                      mock_imapclient):
    uid_dict = uids.example()
    mock_imapclient.add_folder_data(inbox_folder.name, uid_dict)
    inbox_folder.imapfolderinfo = ImapFolderInfo(account=generic_account,
                                                 uidvalidity=1,
                                                 uidnext=1)
    db.session.commit()
    folder_sync_engine = FolderSyncEngine(generic_account.id,
                                          generic_account.namespace.id,
                                          inbox_folder.name,
                                          inbox_folder.id,
                                          generic_account.email_address,
                                          'custom',
                                          BoundedSemaphore(1))
    folder_sync_engine.poll_frequency = 0
    folder_sync_engine.poll_impl()

    saved_uids = db.session.query(ImapUid).filter(
        ImapUid.folder_id == inbox_folder.id)
    assert {u.msg_uid for u in saved_uids} == set(uid_dict)


def test_condstore_flags_refresh(db, default_account, all_mail_folder,
                                 mock_imapclient, monkeypatch):
    monkeypatch.setattr(
        'inbox.mailsync.backends.imap.generic.CONDSTORE_FLAGS_REFRESH_BATCH_SIZE',
        10)
    uid_dict = uids.example()
    mock_imapclient.add_folder_data(all_mail_folder.name, uid_dict)
    mock_imapclient.capabilities = lambda: ['CONDSTORE']

    folder_sync_engine = FolderSyncEngine(default_account.id,
                                          default_account.namespace.id,
                                          all_mail_folder.name,
                                          all_mail_folder.id,
                                          default_account.email_address,
                                          'gmail',
                                          BoundedSemaphore(1))
    folder_sync_engine.initial_sync()

    # Change the labels provided by the mock IMAP server
    for k, v in mock_imapclient._data[all_mail_folder.name].items():
        v['X-GM-LABELS'] = ('newlabel',)
        v['MODSEQ'] = (k,)

    folder_sync_engine.highestmodseq = 0
    folder_sync_engine.poll_impl()
    imapuids = db.session.query(ImapUid). \
        filter_by(folder_id=all_mail_folder.id).all()
    for imapuid in imapuids:
        assert 'newlabel' in [l.name for l in imapuid.labels]

    assert folder_sync_engine.highestmodseq == mock_imapclient.folder_status(
        all_mail_folder.name, ['HIGHESTMODSEQ'])['HIGHESTMODSEQ']


def test_handle_uidinvalid(db, generic_account, inbox_folder, mock_imapclient):
    uid_dict = uids.example()
    mock_imapclient.add_folder_data(inbox_folder.name, uid_dict)
    inbox_folder.imapfolderinfo = ImapFolderInfo(account=generic_account,
                                                 uidvalidity=1,
                                                 uidnext=1)
    db.session.commit()
    folder_sync_engine = FolderSyncEngine(generic_account.id,
                                          generic_account.namespace.id,
                                          inbox_folder.name,
                                          inbox_folder.id,
                                          generic_account.email_address,
                                          'custom',
                                          BoundedSemaphore(1))
    folder_sync_engine.initial_sync()
    mock_imapclient.uidvalidity = 2
    with pytest.raises(UidInvalid):
        folder_sync_engine.poll_impl()

    new_state = folder_sync_engine.resync_uids()

    assert new_state == 'initial'
    assert db.session.query(ImapUid).filter(
        ImapUid.folder_id == inbox_folder.id).all() == []


def test_gmail_initial_sync(db, default_account, all_mail_folder,
                            mock_imapclient):
    uid_dict = uids.example()
    mock_imapclient.add_folder_data(all_mail_folder.name, uid_dict)
    mock_imapclient.list_folders = lambda: [(('\\All', '\\HasNoChildren',),
                                             '/', u'[Gmail]/All Mail')]
    mock_imapclient.idle = lambda: None

    folder_sync_engine = GmailFolderSyncEngine(default_account.id,
                                               default_account.namespace.id,
                                               all_mail_folder.name,
                                               all_mail_folder.id,
                                               default_account.email_address,
                                               'gmail',
                                               BoundedSemaphore(1))
    folder_sync_engine.initial_sync()

    saved_uids = db.session.query(ImapUid).filter(
        ImapUid.folder_id == all_mail_folder.id)
    assert {u.msg_uid for u in saved_uids} == set(uid_dict)


def test_gmail_message_deduplication(db, default_account, all_mail_folder,
                                     trash_folder, mock_imapclient):
    uid = 22
    uid_values = uid_data.example()

    mock_imapclient.list_folders = lambda: [(('\\All', '\\HasNoChildren',),
                                             '/', u'[Gmail]/All Mail'),
                                            (('\\Trash', '\\HasNoChildren',),
                                             '/', u'[Gmail]/Trash')]
    mock_imapclient.idle = lambda: None
    mock_imapclient.add_folder_data(all_mail_folder.name, {uid: uid_values})
    mock_imapclient.add_folder_data(trash_folder.name, {uid: uid_values})

    all_folder_sync_engine = GmailFolderSyncEngine(
        default_account.id, default_account.namespace.id, all_mail_folder.name,
        all_mail_folder.id, default_account.email_address, 'gmail',
        BoundedSemaphore(1))
    all_folder_sync_engine.initial_sync()

    trash_folder_sync_engine = GmailFolderSyncEngine(
        default_account.id, default_account.namespace.id, trash_folder.name,
        trash_folder.id, default_account.email_address, 'gmail',
        BoundedSemaphore(1))
    trash_folder_sync_engine.initial_sync()

    # Check that we have two uids, but just one message.
    assert [(uid,)] == db.session.query(ImapUid.msg_uid).filter(
        ImapUid.folder_id == all_mail_folder.id).all()

    assert [(uid,)] == db.session.query(ImapUid.msg_uid).filter(
        ImapUid.folder_id == trash_folder.id).all()

    assert db.session.query(Message).filter(
        Message.namespace_id == default_account.namespace.id,
        Message.g_msgid == uid_values['X-GM-MSGID']).count() == 1
