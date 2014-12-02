import pytest
from inbox.mailsync.backends.imap.common import remove_messages
from inbox.models import Account, Folder, Message, Thread
from inbox.models.backends.imap import ImapUid
from tests.util.base import add_fake_message, add_fake_thread


def test_deletion(db):
    ACCOUNT_ID = 1
    UID = 380

    account = db.session.query(Account).get(ACCOUNT_ID)
    inbox_folder = account.inbox_folder
    old_number_of_imapuids = len(inbox_folder.imapuids)

    imapuid = db.session.query(ImapUid).filter(
                ImapUid.account_id == ACCOUNT_ID,
                ImapUid.msg_uid == UID).one()

    message_id = imapuid.message_id
    thread_id = imapuid.message.thread_id

    remove_messages(ACCOUNT_ID, db.session, [UID], inbox_folder.name)

    assert len(inbox_folder.imapuids) == old_number_of_imapuids - 1, \
        "only one message should have been deleted"

    total_number_of_uids = db.session.query(ImapUid).join(Folder).filter(
            ImapUid.account_id == ACCOUNT_ID,
            Folder.name == inbox_folder.name).count()

    assert total_number_of_uids == old_number_of_imapuids - 1, \
        "only one message should have been deleted in the db"

    # check that the message was removed from the db too
    msg = db.session.query(Message).get(message_id)
    assert msg == None, "the associated message should have been deleted"

    # test that the associated thread is gone too.
    thread = db.session.query(Thread).get(thread_id)
    assert thread == None, "the associated thread should have been deleted"


def test_deleting_from_a_message_with_multiple_uids(db):
    # Now check that deleting a imapuid from a message with
    # multiple uids doesn't delete the message itself
    ACCOUNT_ID = 1
    NAMESPACE_ID = 1

    account = db.session.query(Account).get(ACCOUNT_ID)
    inbox_folder = account.inbox_folder
    sent_folder = account.sent_folder

    thread = add_fake_thread(db.session, NAMESPACE_ID,)
    message = add_fake_message(db.session, NAMESPACE_ID, thread)

    sent_uid = ImapUid(message=message, account=account, folder=sent_folder,
                       msg_uid=1337)
    inbox_uid = ImapUid(message=message, account=account, folder=inbox_folder,
                        msg_uid=2222)
    db.session.add(sent_uid)
    db.session.add(inbox_uid)
    db.session.commit()

    remove_messages(ACCOUNT_ID, db.session, [2222], inbox_folder.name)

    msg = db.session.query(Message).get(message.id)
    assert msg is not None, "the associated message should not have been deleted"

    assert len(msg.imapuids) == 1, "the message should have only one imapuid"


if __name__ == '__main__':
    pytest.main([__file__])
