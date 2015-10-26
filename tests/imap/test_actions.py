# -*- coding: utf-8 -*-
import mock
from flanker import mime
from inbox.actions.backends.generic import (remote_update_draft,
                                            remote_save_draft)
from inbox.actions.backends.gmail import remote_change_labels
from tests.imap.data import mock_imapclient
from tests.util.base import add_fake_imapuid
from inbox.crispin import writable_connection_pool
from inbox.sendmail.base import create_message_from_json, update_draft


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
                                     default_account.namespace,
                                     db.session,
                                     True)

    draft.is_draft = True
    draft.version = 0
    remote_save_draft(default_account, draft, db.session)
    with pool.get() as conn:
        conn.select_folder('Drafts', lambda *args: True)
        assert len(conn.all_uids()) == 1

    # Check that draft is not resaved if already synced.
    remote_update_draft(default_account, draft, db.session)
    with pool.get() as conn:
        conn.select_folder('Drafts', lambda *args: True)
        assert len(conn.all_uids()) == 1

    # Check that an older version is deleted
    draft.version = 4
    update_draft(db.session, default_account, draft,
                 from_addr=draft.from_addr, subject='New subject', blocks=[])
    remote_update_draft(default_account, draft, db.session)
    with pool.get() as conn:
        conn.select_folder('Drafts', lambda *args: True)
        all_uids = conn.all_uids()
        assert len(all_uids) == 1
        data = conn.uids(all_uids)[0]
        parsed = mime.from_string(data.body)
        expected_message_id = '<{}-{}@mailer.nylas.com>'.format(
            draft.public_id, draft.version)
        assert parsed.headers.get('Message-Id') == expected_message_id


def test_change_labels(db, default_account, message, folder, mock_imapclient):
    mock_imapclient.add_folder_data(folder.name, {})
    mock_imapclient.add_gmail_labels = mock.Mock()
    mock_imapclient.remove_gmail_labels = mock.Mock()
    add_fake_imapuid(db.session, default_account.id, message, folder, 22)

    remote_change_labels(default_account, message.id,
                         db.session,
                         removed_labels=['\\Inbox'],
                         added_labels=[u'motörhead', u'μετάνοια'])
    mock_imapclient.add_gmail_labels.assert_called_with(
        [22], ['mot&APY-rhead', '&A7wDtQPEA6wDvQO,A7kDsQ-'])
    mock_imapclient.remove_gmail_labels.assert_called_with([22], ['\\Inbox'])
