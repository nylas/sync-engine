from flanker import mime
from inbox.actions.backends.generic import (remote_update_draft,
                                            remote_save_draft)
from tests.imap.data import mock_imapclient
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
