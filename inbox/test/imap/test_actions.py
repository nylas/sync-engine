# flake8: noqa: F401, F811
# -*- coding: utf-8 -*-
import mock
import pytest
import gevent
from flanker import mime
from inbox.actions.base import (change_labels, save_draft, update_draft,
                                delete_draft, create_folder, update_folder,
                                delete_folder, create_label, update_label,
                                delete_label, mark_unread, mark_starred)
from inbox.util.testutils import mock_imapclient  # noqa
from inbox.test.util.base import add_fake_imapuid, add_fake_category
from inbox.crispin import writable_connection_pool
from inbox.models import Category, ActionLog
from inbox.models.action_log import schedule_action
from inbox.sendmail.base import create_message_from_json
from inbox.sendmail.base import update_draft as sendmail_update_draft
from inbox.events.actions.backends.gmail import remote_create_event
from inbox.transactions.actions import SyncbackService
from inbox.models.session import new_session
from inbox.actions.backends.generic import _create_email

import pytest
@pytest.mark.only
def test_draft_updates(db, default_account, mock_imapclient):
    # Set up folder list
    mock_imapclient._data['Drafts'] = {}
    mock_imapclient._data['Trash'] = {}
    mock_imapclient._data['Sent Mail'] = {}
    mock_imapclient.list_folders = lambda: [
        (('\\HasNoChildren', '\\Drafts'), '/', 'Drafts'),
        (('\\HasNoChildren', '\\Trash'), '/', 'Trash'),
        (('\\HasNoChildren', '\\Sent'), '/', 'Sent Mail'),
    ]

    pool = writable_connection_pool(default_account.id)

    draft = create_message_from_json({'subject': 'Test draft'},
                                     default_account.namespace, db.session,
                                     True)
    draft.is_draft = True
    draft.version = 0
    db.session.commit()
    with pool.get() as conn:
        save_draft(conn, default_account.id, draft.id, {'version': 0})
        conn.select_folder('Drafts', lambda *args: True)
        assert len(conn.all_uids()) == 1

        # Check that draft is not resaved if already synced.
        update_draft(conn, default_account.id, draft.id, {'version': 0})
        conn.select_folder('Drafts', lambda *args: True)
        assert len(conn.all_uids()) == 1

        # Check that an older version is deleted
        draft.version = 4
        sendmail_update_draft(db.session, default_account, draft,
                              from_addr=draft.from_addr, subject='New subject',
                              blocks=[])
        db.session.commit()

        update_draft(conn, default_account.id, draft.id, {'version': 5})

        conn.select_folder('Drafts', lambda *args: True)
        all_uids = conn.all_uids()
        assert len(all_uids) == 1
        data = conn.uids(all_uids)[0]
        parsed = mime.from_string(data.body)
        expected_message_id = '<{}-{}@mailer.nylas.com>'.format(
            draft.public_id, draft.version)
        assert parsed.headers.get('Message-Id') == expected_message_id

        # We're testing the draft deletion with Gmail here. However,
        # because of a race condition in Gmail's reconciliation algorithm,
        # we need to check if the sent mail has been created in the sent
        # folder. Since we're mocking everything, we have to create it
        # ourselves.
        mock_imapclient.append('Sent Mail', data.body, None, None,
                               x_gm_msgid=4323)

        delete_draft(conn, default_account.id, draft.id,
                 {'message_id_header': draft.message_id_header,
                  'nylas_uid': draft.nylas_uid, 'version': 5})

        conn.select_folder('Drafts', lambda *args: True)
        all_uids = conn.all_uids()
        assert len(all_uids) == 0


def test_change_flags(db, default_account, message, folder, mock_imapclient):
    mock_imapclient.add_folder_data(folder.name, {})
    mock_imapclient.add_flags = mock.Mock()
    mock_imapclient.remove_flags = mock.Mock()
    add_fake_imapuid(db.session, default_account.id, message, folder, 22)
    with writable_connection_pool(default_account.id).get() as crispin_client:
        mark_unread(crispin_client, default_account.id, message.id,
                    {'unread': False})
        mock_imapclient.add_flags.assert_called_with([22], ['\\Seen'], silent=True)

        mark_unread(crispin_client, default_account.id, message.id,
                    {'unread': True})
        mock_imapclient.remove_flags.assert_called_with([22], ['\\Seen'], silent=True)

        mark_starred(crispin_client, default_account.id, message.id,
                     {'starred': True})
        mock_imapclient.add_flags.assert_called_with([22], ['\\Flagged'], silent=True)

        mark_starred(crispin_client, default_account.id, message.id,
                     {'starred': False})
        mock_imapclient.remove_flags.assert_called_with([22], ['\\Flagged'], silent=True)


def test_change_labels(db, default_account, message, folder, mock_imapclient):
    mock_imapclient.add_folder_data(folder.name, {})
    mock_imapclient.add_gmail_labels = mock.Mock()
    mock_imapclient.remove_gmail_labels = mock.Mock()
    add_fake_imapuid(db.session, default_account.id, message, folder, 22)

    with writable_connection_pool(default_account.id).get() as crispin_client:
        change_labels(crispin_client, default_account.id, [message.id],
                      {'removed_labels': ['\\Inbox'],
                       'added_labels': [u'motörhead', u'μετάνοια']})
        mock_imapclient.add_gmail_labels.assert_called_with(
            [22], ['mot&APY-rhead', '&A7wDtQPEA6wDvQO,A7kDsQ-'], silent=True)
        mock_imapclient.remove_gmail_labels.assert_called_with([22], ['\\Inbox'],
                                                               silent=True)


@pytest.mark.parametrize('obj_type', ['folder', 'label'])
def test_folder_crud(db, default_account, mock_imapclient, obj_type):
    mock_imapclient.create_folder = mock.Mock()
    mock_imapclient.rename_folder = mock.Mock()
    mock_imapclient.delete_folder = mock.Mock()
    cat = add_fake_category(db.session, default_account.namespace.id,
                            'MyFolder')
    with writable_connection_pool(default_account.id).get() as crispin_client:
        if obj_type == 'folder':
            create_folder(crispin_client, default_account.id, cat.id)
        else:
            create_label(crispin_client, default_account.id, cat.id)
        mock_imapclient.create_folder.assert_called_with('MyFolder')

        cat.display_name = 'MyRenamedFolder'
        db.session.commit()
        if obj_type == 'folder':
            update_folder(crispin_client, default_account.id, cat.id,
                          {'old_name': 'MyFolder',
                           'new_name': 'MyRenamedFolder'})
        else:
            update_label(crispin_client, default_account.id, cat.id,
                         {'old_name': 'MyFolder',
                          'new_name': 'MyRenamedFolder'})
        mock_imapclient.rename_folder.assert_called_with('MyFolder',
                                                         'MyRenamedFolder')

        category_id = cat.id
        if obj_type == 'folder':
            delete_folder(crispin_client, default_account.id, cat.id)
        else:
            delete_label(crispin_client, default_account.id, cat.id)
    mock_imapclient.delete_folder.assert_called_with('MyRenamedFolder')
    db.session.commit()
    assert db.session.query(Category).get(category_id) is None

@pytest.yield_fixture
def patched_syncback_task(monkeypatch):
    # Ensures 'create_event' actions fail and all others succeed
    def function_for_action(name):
        def func(*args):
            if name == 'create_event':
                raise Exception("Failed to create remote event")
        return func

    monkeypatch.setattr("inbox.transactions.actions.function_for_action", function_for_action)
    monkeypatch.setattr("inbox.transactions.actions.ACTION_MAX_NR_OF_RETRIES", 1)
    yield
    monkeypatch.undo()

# Test that failing to create a remote copy of an event marks all pending actions
# for that event as failed.
def test_failed_event_creation(db, patched_syncback_task, default_account, event):
    schedule_action('create_event', event, default_account.namespace.id, db.session)
    schedule_action('update_event', event, default_account.namespace.id, db.session)
    schedule_action('update_event', event, default_account.namespace.id, db.session)
    schedule_action('delete_event', event, default_account.namespace.id, db.session)
    db.session.commit()

    NUM_WORKERS = 2
    service = SyncbackService(syncback_id=0, process_number=0,
        total_processes=NUM_WORKERS, num_workers=NUM_WORKERS)
    service._restart_workers()
    service._process_log()

    while not service.task_queue.empty():
        gevent.sleep(0.1)

    # This has to be a separate while-loop because there's a brief moment where
    # the task queue is empty, but num_idle_workers hasn't been updated yet.
    # On slower systems, we might need to sleep a bit between the while-loops.
    while service.num_idle_workers != NUM_WORKERS:
        gevent.sleep(0.1)

    q = db.session.query(ActionLog).filter_by(record_id=event.id).all()
    assert all(a.status == 'failed' for a in q)
