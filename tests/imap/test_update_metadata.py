from inbox.crispin import GmailFlags
from inbox.mailsync.backends.imap.common import update_metadata
from tests.util.base import (add_fake_message, add_fake_thread,
                             add_fake_imapuid)

ACCOUNT_ID = 1
NAMESPACE_ID = 1


def test_update_metadata(db, folder):
    """Check that threads are updated correctly when a label that we haven't
    seen before is added to multiple threads -- previously, this would fail
    with an IntegrityError because autoflush was disabled."""
    first_thread = add_fake_thread(db.session, NAMESPACE_ID)
    second_thread = add_fake_thread(db.session, NAMESPACE_ID)
    uids = []

    first_thread_uids = (22222, 22223)
    for msg_uid in first_thread_uids:
        message = add_fake_message(db.session, NAMESPACE_ID, first_thread)
        uids.append(add_fake_imapuid(db.session, ACCOUNT_ID, message, folder,
                                     msg_uid))

    second_thread_uids = (22224, 22226)
    for msg_uid in second_thread_uids:
        message = add_fake_message(db.session, NAMESPACE_ID, second_thread)
        uids.append(add_fake_imapuid(db.session, ACCOUNT_ID, message, folder,
                                     msg_uid))
    db.session.add_all(uids)
    db.session.commit()

    msg_uids = first_thread_uids + second_thread_uids

    new_flags = {msg_uid: GmailFlags((), (u'\\some_new_label',))
                 for msg_uid in msg_uids}
    update_metadata(ACCOUNT_ID, db.session, folder.name, folder.id, msg_uids,
                    new_flags)
    db.session.commit()
    assert 'some_new_label' in [tag.name for tag in first_thread.tags]
    assert 'some_new_label' in [tag.name for tag in second_thread.tags]


def test_unread_and_draft_tags_applied(db, thread, message, folder, imapuid):
    """Test that the unread and draft tags are added/removed from a thread
    after UID flag changes."""
    msg_uid = imapuid.msg_uid
    update_metadata(ACCOUNT_ID, db.session, folder.name, folder.id, [msg_uid],
                    {msg_uid: GmailFlags((u'\\Seen',), (u'\\Draft',))})
    assert 'unread' not in [t.name for t in thread.tags]
    assert 'drafts' in [t.name for t in thread.tags]
    assert message.is_read

    update_metadata(ACCOUNT_ID, db.session, folder.name, folder.id, [msg_uid],
                    {msg_uid: GmailFlags((), ())})
    assert 'unread' in [t.name for t in thread.tags]
    assert 'drafts' not in [t.name for t in thread.tags]
    assert not message.is_read
    assert message.state == 'sent'


def test_gmail_label_sync(db, default_account, message, thread, folder,
                          imapuid):
    if default_account.important_folder is not None:
        db.session.delete(default_account.important_folder)

    msg_uid = imapuid.msg_uid

    # Note that IMAPClient parses numeric labels into integer types. We have to
    # correctly handle those too.
    new_flags = {
        msg_uid: GmailFlags((), (u'\\Important', u'\\Starred', u'foo', 42))
    }
    update_metadata(ACCOUNT_ID, db.session, folder.name, folder.id, [msg_uid],
                    new_flags)
    thread_tag_names = {tag.name for tag in thread.tags}
    assert {'important', 'starred', 'foo'}.issubset(thread_tag_names)
