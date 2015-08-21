from inbox.crispin import GmailFlags
from inbox.mailsync.backends.imap.common import update_metadata


def test_gmail_label_sync(db, default_account, message, folder,
                          imapuid, default_namespace):
    msg_uid = imapuid.msg_uid

    # Note that IMAPClient parses numeric labels into integer types. We have to
    # correctly handle those too.
    new_flags = {
        msg_uid: GmailFlags((), (u'\\Important', u'\\Starred', u'foo', 42))
    }
    update_metadata(default_namespace.account.id,
                    folder.id, new_flags, db.session)
    category_canonical_names = {c.name for c in message.categories}
    category_display_names = {c.display_name for c in message.categories}
    assert 'important' in category_canonical_names
    assert {'foo', '42'}.issubset(category_display_names)
