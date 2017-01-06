import pytest
import json
from inbox.crispin import GmailFlags, Flags
from inbox.models.backends.imap import ImapUid
from inbox.mailsync.backends.imap.common import (update_metadata,
                                                 update_message_metadata)
from inbox.test.util.base import (add_fake_message, add_fake_imapuid,
                             add_fake_folder, add_fake_thread)


def test_gmail_label_sync(db, default_account, message, folder,
                          imapuid, default_namespace):
    # Note that IMAPClient parses numeric labels into integer types. We have to
    # correctly handle those too.
    new_flags = {
        imapuid.msg_uid: GmailFlags((),
                                    (u'\\Important', u'\\Starred', u'foo', 42),
                                    None)
    }
    update_metadata(default_namespace.account.id,
                    folder.id, folder.canonical_name, new_flags, db.session)
    category_canonical_names = {c.name for c in message.categories}
    category_display_names = {c.display_name for c in message.categories}
    assert 'important' in category_canonical_names
    assert {'foo', '42'}.issubset(category_display_names)


def test_gmail_drafts_flag_constrained_by_folder(db, default_account, message,
                                                 imapuid, folder):
    new_flags = {imapuid.msg_uid: GmailFlags((), (u'\\Draft',), None)}
    update_metadata(default_account.id, folder.id, 'all', new_flags,
                    db.session)
    assert message.is_draft
    update_metadata(default_account.id, folder.id, 'trash', new_flags,
                    db.session)
    assert not message.is_draft


@pytest.mark.parametrize('folder_role', ['drafts', 'trash', 'archive'])
def test_generic_drafts_flag_constrained_by_folder(db, generic_account,
                                                   folder_role):
    msg_uid = 22
    thread = add_fake_thread(db.session, generic_account.namespace.id)
    message = add_fake_message(db.session, generic_account.namespace.id,
                               thread)
    folder = add_fake_folder(db.session, generic_account)
    add_fake_imapuid(db.session, generic_account.id, message, folder, msg_uid)

    new_flags = {msg_uid: Flags(('\\Draft',), None)}
    update_metadata(generic_account.id, folder.id, folder_role, new_flags,
                    db.session)
    assert message.is_draft == (folder_role == 'drafts')


def test_update_categories_when_actionlog_entry_missing(
        db, default_account, message, imapuid):
    message.categories_changes = True
    db.session.commit()
    update_message_metadata(db.session, imapuid.account, message, False)
    assert message.categories == {imapuid.folder.category}


def test_truncate_imapuid_extra_flags(db, default_account, message, folder):

    imapuid = ImapUid(message=message, account_id=default_account.id,
                      msg_uid=2222, folder=folder)
    imapuid.update_flags(['We', 'the', 'People', 'of', 'the', 'United',
                          'States', 'in', 'Order', 'to', 'form', 'a', 'more',
                          'perfect', 'Union', 'establish', 'Justice',
                          'insure', 'domestic', 'Tranquility', 'provide',
                          'for', 'the', 'common', 'defence', 'promote', 'the',
                          'general', 'Welfare', 'and', 'secure', 'the',
                          'Blessings', 'of', 'Liberty', 'to', 'ourselves',
                          'and', 'our', 'Posterity', 'do', 'ordain', 'and',
                          'establish', 'this', 'Constitution', 'for', 'the',
                          'United', 'States', 'of', 'America'])

    assert len(json.dumps(imapuid.extra_flags)) < 255
