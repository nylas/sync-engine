# flake8: noqa: F401, F811
from datetime import datetime, timedelta
import pytest
from sqlalchemy import desc
import gevent
from gevent.lock import Semaphore
from sqlalchemy.orm.exc import ObjectDeletedError
from inbox.crispin import GmailFlags
from inbox.mailsync.backends.imap.common import (remove_deleted_uids,
                                                 update_metadata)
from inbox.mailsync.gc import DeleteHandler, LabelRenameHandler
from inbox.models import Folder, Transaction
from inbox.models.label import Label
from tests.util.base import add_fake_imapuid, add_fake_message
from tests.imap.data import mock_imapclient, MockIMAPClient


@pytest.fixture()
def marked_deleted_message(db, message):
    deleted_timestamp = datetime(2015, 2, 22, 22, 22, 22)
    message.deleted_at = deleted_timestamp
    db.session.commit()
    return message


def test_messages_deleted_asynchronously(db, default_account, thread, message,
                                         imapuid, folder):
    msg_uid = imapuid.msg_uid
    update_metadata(default_account.id, folder.id, folder.canonical_name,
                    {msg_uid: GmailFlags((), ('label',), None)}, db.session)
    assert 'label' in [cat.display_name for cat in message.categories]
    remove_deleted_uids(default_account.id, folder.id, [msg_uid])
    db.session.expire_all()
    assert abs((message.deleted_at - datetime.utcnow()).total_seconds()) < 2
    # Check that message categories do get updated synchronously.
    assert 'label' not in [cat.display_name for cat in message.categories]


def test_drafts_deleted_synchronously(db, default_account, thread, message,
                                      imapuid, folder):
    message.is_draft = True
    db.session.commit()
    msg_uid = imapuid.msg_uid
    remove_deleted_uids(default_account.id, folder.id, [msg_uid])
    db.session.expire_all()
    with pytest.raises(ObjectDeletedError):
        message.id
    with pytest.raises(ObjectDeletedError):
        thread.id


def test_deleting_from_a_message_with_multiple_uids(db, default_account,
                                                    message, thread):
    """Check that deleting a imapuid from a message with
    multiple uids doesn't mark the message for deletion."""
    inbox_folder = Folder.find_or_create(db.session, default_account, 'inbox',
                                         'inbox')
    sent_folder = Folder.find_or_create(db.session, default_account, 'sent',
                                        'sent')

    add_fake_imapuid(db.session, default_account.id, message, sent_folder,
                     1337)
    add_fake_imapuid(db.session, default_account.id, message, inbox_folder,
                     2222)

    assert len(message.imapuids) == 2

    remove_deleted_uids(default_account.id, inbox_folder.id, [2222])
    db.session.expire_all()

    assert message.deleted_at is None, \
        "The associated message should not have been marked for deletion."

    assert len(message.imapuids) == 1, \
        "The message should have only one imapuid."


def test_deletion_with_short_ttl(db, default_account, default_namespace,
                                 marked_deleted_message, thread, folder):
    handler = DeleteHandler(account_id=default_account.id,
                            namespace_id=default_namespace.id,
                            provider_name=default_account.provider,
                            uid_accessor=lambda m: m.imapuids,
                            message_ttl=0)
    handler.check(marked_deleted_message.deleted_at + timedelta(seconds=1))
    db.session.expire_all()
    # Check that objects were actually deleted
    with pytest.raises(ObjectDeletedError):
        marked_deleted_message.id
    with pytest.raises(ObjectDeletedError):
        thread.id


def test_non_orphaned_messages_get_unmarked(db, default_account,
                                            default_namespace,
                                            marked_deleted_message, thread,
                                            folder, imapuid):
    handler = DeleteHandler(account_id=default_account.id,
                            namespace_id=default_namespace.id,
                            provider_name=default_account.provider,
                            uid_accessor=lambda m: m.imapuids,
                            message_ttl=0)
    handler.check(marked_deleted_message.deleted_at + timedelta(seconds=1))
    db.session.expire_all()
    # message actually has an imapuid associated, so check that the
    # DeleteHandler unmarked it.
    assert marked_deleted_message.deleted_at is None


def test_threads_only_deleted_when_no_messages_left(db, default_account,
                                                    default_namespace,
                                                    marked_deleted_message,
                                                    thread, folder):
    handler = DeleteHandler(account_id=default_account.id,
                            namespace_id=default_namespace.id,
                            provider_name=default_account.provider,
                            uid_accessor=lambda m: m.imapuids,
                            message_ttl=0)
    # Add another message onto the thread
    add_fake_message(db.session, default_namespace.id, thread)

    handler.check(marked_deleted_message.deleted_at + timedelta(seconds=1))
    db.session.expire_all()
    # Check that the orphaned message was deleted.
    with pytest.raises(ObjectDeletedError):
        marked_deleted_message.id
    # Would raise ObjectDeletedError if thread was deleted.
    thread.id


def test_deletion_deferred_with_longer_ttl(db, default_account,
                                           default_namespace,
                                           marked_deleted_message, thread,
                                           folder):
    handler = DeleteHandler(account_id=default_account.id,
                            namespace_id=default_namespace.id,
                            provider_name=default_account.provider,
                            uid_accessor=lambda m: m.imapuids,
                            message_ttl=5)
    db.session.commit()

    handler.check(marked_deleted_message.deleted_at + timedelta(seconds=1))
    # Would raise ObjectDeletedError if objects were deleted
    marked_deleted_message.id
    thread.id


def test_deletion_creates_revision(db, default_account, default_namespace,
                                   marked_deleted_message, thread, folder):
    message_id = marked_deleted_message.id
    thread_id = thread.id
    handler = DeleteHandler(account_id=default_account.id,
                            namespace_id=default_namespace.id,
                            provider_name=default_account.provider,
                            uid_accessor=lambda m: m.imapuids,
                            message_ttl=0)
    handler.check(marked_deleted_message.deleted_at + timedelta(seconds=1))
    db.session.commit()
    latest_message_transaction = db.session.query(Transaction). \
        filter(Transaction.record_id == message_id,
               Transaction.object_type == 'message',
               Transaction.namespace_id == default_namespace.id). \
        order_by(desc(Transaction.id)).first()
    assert latest_message_transaction.command == 'delete'

    latest_thread_transaction = db.session.query(Transaction). \
        filter(Transaction.record_id == thread_id,
               Transaction.object_type == 'thread',
               Transaction.namespace_id == default_namespace.id). \
        order_by(desc(Transaction.id)).first()
    assert latest_thread_transaction.command == 'delete'


def test_deleted_labels_get_gced(empty_db, default_account, thread, message,
                                 imapuid, folder):
    # Check that only the labels without messages attached to them
    # get deleted.
    default_namespace = default_account.namespace

    # Create a label w/ no messages attached.
    label = Label.find_or_create(empty_db.session, default_account,
                                 'dangling label')
    label.deleted_at = datetime.utcnow()
    label.category.deleted_at = datetime.utcnow()
    label_id = label.id
    empty_db.session.commit()

    # Create a label with attached messages.
    msg_uid = imapuid.msg_uid
    update_metadata(default_account.id, folder.id, folder.canonical_name,
                    {msg_uid: GmailFlags((), ('label',), None)}, empty_db.session)

    label_ids = []
    for cat in message.categories:
        for l in cat.labels:
            label_ids.append(l.id)

    handler = DeleteHandler(account_id=default_account.id,
                            namespace_id=default_namespace.id,
                            provider_name=default_account.provider,
                            uid_accessor=lambda m: m.imapuids,
                            message_ttl=0)
    handler.gc_deleted_categories()
    empty_db.session.commit()

    # Check that the first label got gc'ed
    marked_deleted = empty_db.session.query(Label).get(label_id)
    assert marked_deleted is None

    # Check that the other labels didn't.
    for label_id in label_ids:
        assert empty_db.session.query(Label).get(label_id) is not None


def test_renamed_label_refresh(db, default_account, thread, message,
                               imapuid, folder, mock_imapclient, monkeypatch):
    # Check that imapuids see their labels refreshed after running
    # the LabelRenameHandler.
    msg_uid = imapuid.msg_uid
    uid_dict = {msg_uid: GmailFlags((), ('stale label',), ('23',))}

    update_metadata(default_account.id, folder.id, folder.canonical_name,
                    uid_dict, db.session)

    new_flags = {msg_uid: {'FLAGS': ('\\Seen',), 'X-GM-LABELS': ('new label',),
                           'MODSEQ': ('23',)}}
    mock_imapclient._data['[Gmail]/All mail'] = new_flags

    mock_imapclient.add_folder_data(folder.name, new_flags)

    monkeypatch.setattr(MockIMAPClient, 'search',
                        lambda x, y: [msg_uid])

    semaphore = Semaphore(value=1)

    rename_handler = LabelRenameHandler(default_account.id,
                                        default_account.namespace.id,
                                        'new label', semaphore)

    # Acquire the semaphore to check that LabelRenameHandlers block if
    # the semaphore is in-use.
    semaphore.acquire()
    rename_handler.start()

    # Wait 10 secs and check that the data hasn't changed.
    gevent.sleep(10)

    labels = list(imapuid.labels)
    assert len(labels) == 1
    assert labels[0].name == 'stale label'
    semaphore.release()
    rename_handler.join()

    db.session.refresh(imapuid)
    # Now check that the label got updated.
    labels = list(imapuid.labels)
    assert len(labels) == 1
    assert labels[0].name == 'new label'


def test_reply_to_message_cascade(db, default_namespace, thread, message):
    reply = add_fake_message(db.session, default_namespace.id, thread)
    reply.reply_to_message = message
    db.session.commit()

    db.session.expire_all()
    db.session.delete(message)
    db.session.commit()
