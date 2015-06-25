import datetime
from inbox.models.folder import Folder, FolderItem
from inbox.models.tag import Tag
from inbox.models.message import Message
from inbox.models.backends.imap import ImapUid
from inbox.mailsync.backends.imap.common import (recompute_thread_labels,
                                                 add_any_new_thread_labels,
                                                 update_unread_status)
from tests.util.base import add_fake_message, add_fake_imapuid


def test_recompute_thread_labels(db, thread, default_namespace):
    # This is smoke test that checks that a lone label gets
    # added to a thread's labels.
    account = default_namespace.account
    message = add_fake_message(db.session, default_namespace.id, thread)
    add_fake_imapuid(db.session, account.id, message,
                     account.inbox_folder, 22)
    g_labels = thread.messages[-1].imapuids[-1].g_labels

    g_labels.append('Random-label-1')
    recompute_thread_labels(thread, db.session)
    folders = {folder.name: folder for folder in thread.folders}
    assert 'Random-label-1' in folders


def test_recompute_thread_labels_removes_trash(db, default_account, thread):
    default_account.trash_folder = Folder(name='Trash',
                                          account_id=default_account.id)
    message = add_fake_message(db.session, default_account.namespace.id,
                               thread)
    add_fake_imapuid(db.session, default_account.id, message,
                     default_account.inbox_folder, 22)
    db.session.commit()

    # Check that the we remove the trash folder from a thread
    # if the latest message has the inbox flag.
    # To do this, we manufacture this situation.
    g_labels = thread.messages[-1].imapuids[-1].g_labels
    if '\\Inbox' not in g_labels:
        g_labels.append('\\Inbox')

    thread.folders.add(default_account.trash_folder)
    recompute_thread_labels(thread, db.session)
    assert default_account.trash_folder not in thread.folders,\
        "should have removed trash folder from thread"


def test_adding_message_to_thread(db, default_account, thread):
    """recompute_thread_labels is not invoked when a new message is added
     (only when UID metadata changes, or when a UID is deleted). Test that
     tag changes work when adding messages to a thread."""
    default_account.trash_folder = Folder(name='Trash', account=default_account)
    FolderItem(thread=thread, folder=default_account.trash_folder)

    folder_names = [folder.name for folder in thread.folders]
    m = Message(namespace_id=default_account.namespace.id,
                subject='test message', thread_id=thread.id,
                received_date=datetime.datetime.now(),
                size=64, body="body", snippet="snippet")

    uid = ImapUid(account=default_account, message=m,
                  g_labels=['\\Inbox', 'test-label'],
                  msg_uid=22L, folder_id=default_account.inbox_folder.id)
    uid.folder = default_account.inbox_folder
    uid2 = ImapUid(account=default_account, message=m, g_labels=['test-2'],
                   msg_uid=24L, folder_id=default_account.trash_folder.id)
    uid2.folder = default_account.trash_folder

    thread.messages.append(m)
    add_any_new_thread_labels(thread, uid, db.session)
    add_any_new_thread_labels(thread, uid2, db.session)

    folder_names = [folder.name for folder in thread.folders]
    for folder in folder_names:
        assert folder in ['Inbox', 'Trash', 'test-label', 'test-2', '[Gmail]/All Mail', '[Gmail]/Important'],\
            "all folders should be present"

    # Now, remove the message
    m.imapuids.remove(uid2)
    db.session.delete(uid2)
    db.session.flush()

    recompute_thread_labels(thread, db.session)
    folder_names = [folder.name for folder in thread.folders]
    assert 'test-2' not in folder_names,\
        "test-2 label should have been removed from thread"


def test_update_unread_status(db, thread, message, imapuid):
    message.is_read = True
    imapuid.is_seen = False
    update_unread_status(imapuid)

    assert message.is_read is False, "message shouldn't be read"

    tag_names = [tag.name for tag in thread.tags]
    assert 'unread' in tag_names, "thread should be unread"

    imapuid.is_seen = True
    update_unread_status(imapuid)

    assert message.is_read is True, "message should be read"

    tag_names = [tag.name for tag in thread.tags]
    assert 'unread' not in tag_names, "thread should be read"


def test_tag_deletion_removes_it_from_thread(db, thread):
    tag = Tag(namespace_id=thread.namespace_id,
              name='RandomTag123')
    thread.apply_tag(tag)
    db.session.commit()

    assert 'RandomTag123' in [t.name for t in thread.tags]

    db.session.delete(tag)
    db.session.commit()

    assert 'RandomTag123' not in [t.name for t in thread.tags]
