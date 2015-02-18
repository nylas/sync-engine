from datetime import datetime
import pytest
from sqlalchemy.orm.exc import ObjectDeletedError
from inbox.crispin import GmailFlags
from inbox.mailsync.backends.imap.common import (remove_deleted_uids,
                                                 update_metadata)
from inbox.mailsync.gc import DeleteHandler
from tests.util.base import add_fake_imapuid, add_fake_message


def test_only_uids_deleted_synchronously(db, default_account,
                                         default_namespace, thread, message,
                                         imapuid, folder):
    msg_uid = imapuid.msg_uid
    update_metadata(default_account.id, db.session, folder.name, folder.id,
                    [msg_uid], {msg_uid: GmailFlags((), ('label',))})
    assert 'label' in [t.name for t in thread.tags]
    remove_deleted_uids(default_account.id, db.session, [msg_uid], folder.id)
    assert abs((message.deleted_at - datetime.utcnow()).total_seconds()) < 2
    # Check that thread tags do get updated synchronously.
    assert 'label' not in [t.name for t in thread.tags]


def test_deleting_from_a_message_with_multiple_uids(db, default_account,
                                                    message, thread):
    """Check that deleting a imapuid from a message with
    multiple uids doesn't mark the message for deletion."""
    inbox_folder = default_account.inbox_folder
    sent_folder = default_account.sent_folder

    add_fake_imapuid(db.session, default_account.id, message, sent_folder,
                     1337)
    add_fake_imapuid(db.session, default_account.id, message, inbox_folder,
                     2222)

    assert len(message.imapuids) == 2

    remove_deleted_uids(default_account.id, db.session, [2222],
                        inbox_folder.id)

    assert message.deleted_at is None, \
        "The associated message should not have been marked for deletion."

    assert len(message.imapuids) == 1, \
        "The message should have only one imapuid."


def test_deletion_with_short_ttl(db, default_account, default_namespace,
                                 message, thread, folder, imapuid):
    msg_uid = imapuid.msg_uid
    handler = DeleteHandler(account_id=default_account.id,
                            namespace_id=default_namespace.id,
                            uid_accessor=lambda m: m.imapuids,
                            message_ttl=0)
    remove_deleted_uids(default_account.id, db.session, [msg_uid], folder.id)
    handler.check()
    # Check that objects were actually deleted
    with pytest.raises(ObjectDeletedError):
        message.id
    with pytest.raises(ObjectDeletedError):
        thread.id


def test_non_orphaned_messages_get_unmarked(db, default_account,
                                            default_namespace, message, thread,
                                            folder, imapuid):
    message.deleted_at = datetime.utcnow()
    db.session.commit()
    handler = DeleteHandler(account_id=default_account.id,
                            namespace_id=default_namespace.id,
                            uid_accessor=lambda m: m.imapuids,
                            message_ttl=0)
    handler.check()
    # message actually has an imapuid associated, so check that the
    # DeleteHandler unmarked it.
    assert message.deleted_at is None


def test_threads_only_deleted_when_no_messages_left(db, default_account,
                                                    default_namespace, message,
                                                    thread, folder, imapuid):
    msg_uid = imapuid.msg_uid
    handler = DeleteHandler(account_id=default_account.id,
                            namespace_id=default_namespace.id,
                            uid_accessor=lambda m: m.imapuids,
                            message_ttl=0)
    # Add another message onto the thread
    add_fake_message(db.session, default_namespace.id, thread)
    remove_deleted_uids(default_account.id, db.session, [msg_uid], folder.id)
    handler.check()
    # Check that the orphaned message was deleted.
    with pytest.raises(ObjectDeletedError):
        message.id
    # Would raise ObjectDeletedError if thread was deleted.
    thread.id


def test_deletion_deferred_with_longer_ttl(db, default_account,
                                           default_namespace, message, thread,
                                           folder, imapuid):
    msg_uid = imapuid.msg_uid
    handler = DeleteHandler(account_id=default_account.id,
                            namespace_id=default_namespace.id,
                            uid_accessor=lambda m: m.imapuids,
                            message_ttl=1)
    remove_deleted_uids(default_account.id, db.session, [msg_uid], folder.id)
    handler.check()
    # Would raise ObjectDeletedError if objects were deleted
    message.id
    thread.id
