# -*- coding: utf-8 -*-
import mock
import pytest
from flanker import mime
from flanker.addresslib import address
from inbox.actions.base import (change_labels, save_draft, update_draft,
                                delete_draft, create_folder, update_folder,
                                delete_folder, create_label, update_label,
                                delete_label, mark_unread, mark_starred)
from tests.imap.data import mock_imapclient  # noqa
from tests.util.base import add_fake_imapuid, add_fake_category
from inbox.crispin import writable_connection_pool
from inbox.models import Category
from inbox.sendmail.base import create_message_from_json
from inbox.sendmail.base import update_draft as sendmail_update_draft


def test_draft_updates(db, default_account, mock_imapclient):
    # Set up folder list
    mock_imapclient._data['Drafts'] = {}
    mock_imapclient._data['Trash'] = {}
    mock_imapclient.list_folders = lambda: [
        (('\\HasNoChildren', '\\Drafts'), '/', 'Drafts'),
        (('\\HasNoChildren', '\\Trash'), '/', 'Trash')
    ]

    pool = writable_connection_pool(default_account.id)

    draft = create_message_from_json({'subject': 'Test draft'},
                                     default_account.namespace, db.session,
                                     True)

    draft.is_draft = True
    draft.version = 0
    db.session.commit()
    save_draft(default_account.id, draft.id, {'version': 0})
    with pool.get() as conn:
        conn.select_folder('Drafts', lambda *args: True)
        assert len(conn.all_uids()) == 1

    # Check that draft is not resaved if already synced.
    update_draft(default_account.id, draft.id, {'version': 0})
    with pool.get() as conn:
        conn.select_folder('Drafts', lambda *args: True)
        assert len(conn.all_uids()) == 1

    # Check that an older version is deleted
    draft.version = 4
    sendmail_update_draft(db.session, default_account, draft,
                          from_addr=draft.from_addr, subject='New subject',
                          blocks=[])
    db.session.commit()

    update_draft(default_account.id, draft.id, {'version': 5})
    with pool.get() as conn:
        conn.select_folder('Drafts', lambda *args: True)
        all_uids = conn.all_uids()
        assert len(all_uids) == 1
        data = conn.uids(all_uids)[0]
        parsed = mime.from_string(data.body)
        expected_hostname = address.parse(parsed.headers['From']).hostname
        expected_message_id = '<{}-{}@{}>'.format(
            draft.public_id, draft.version, expected_hostname)
        assert parsed.headers.get('Message-Id') == expected_message_id

    delete_draft(default_account.id, draft.id,
                 {'message_id_header': draft.message_id_header,
                  'inbox_uid': draft.inbox_uid, 'version': 5})
    with pool.get() as conn:
        conn.select_folder('Drafts', lambda *args: True)
        all_uids = conn.all_uids()
        assert len(all_uids) == 0


def test_change_flags(db, default_account, message, folder, mock_imapclient):
    mock_imapclient.add_folder_data(folder.name, {})
    mock_imapclient.add_flags = mock.Mock()
    mock_imapclient.remove_flags = mock.Mock()
    add_fake_imapuid(db.session, default_account.id, message, folder, 22)
    mark_unread(default_account.id, message.id, {'unread': False})
    mock_imapclient.add_flags.assert_called_with([22], ['\\Seen'])

    mark_unread(default_account.id, message.id, {'unread': True})
    mock_imapclient.remove_flags.assert_called_with([22], ['\\Seen'])

    mark_starred(default_account.id, message.id, {'starred': True})
    mock_imapclient.add_flags.assert_called_with([22], ['\\Flagged'])

    mark_starred(default_account.id, message.id, {'starred': False})
    mock_imapclient.remove_flags.assert_called_with([22], ['\\Flagged'])


def test_change_labels(db, default_account, message, folder, mock_imapclient):
    mock_imapclient.add_folder_data(folder.name, {})
    mock_imapclient.add_gmail_labels = mock.Mock()
    mock_imapclient.remove_gmail_labels = mock.Mock()
    add_fake_imapuid(db.session, default_account.id, message, folder, 22)

    change_labels(default_account.id, message.id,
                  {'removed_labels': ['\\Inbox'],
                   'added_labels': [u'motörhead', u'μετάνοια']})
    mock_imapclient.add_gmail_labels.assert_called_with(
        [22], ['mot&APY-rhead', '&A7wDtQPEA6wDvQO,A7kDsQ-'])
    mock_imapclient.remove_gmail_labels.assert_called_with([22], ['\\Inbox'])


@pytest.mark.parametrize('obj_type', ['folder', 'label'])
def test_folder_crud(db, default_account, mock_imapclient, obj_type):
    mock_imapclient.create_folder = mock.Mock()
    mock_imapclient.rename_folder = mock.Mock()
    mock_imapclient.delete_folder = mock.Mock()
    cat = add_fake_category(db.session, default_account.namespace.id,
                            'MyFolder')
    if obj_type == 'folder':
        create_folder(default_account.id, cat.id)
    else:
        create_label(default_account.id, cat.id)
    mock_imapclient.create_folder.assert_called_with('MyFolder')

    cat.display_name = 'MyRenamedFolder'
    db.session.commit()
    if obj_type == 'folder':
        update_folder(default_account.id, cat.id, {'old_name': 'MyFolder'})
    else:
        update_label(default_account.id, cat.id, {'old_name': 'MyFolder'})
    mock_imapclient.rename_folder.assert_called_with('MyFolder',
                                                     'MyRenamedFolder')

    category_id = cat.id
    if obj_type == 'folder':
        delete_folder(default_account.id, cat.id)
    else:
        delete_label(default_account.id, cat.id)
    mock_imapclient.delete_folder.assert_called_with('MyRenamedFolder')
    db.session.commit()
    assert db.session.query(Category).get(category_id) is None
