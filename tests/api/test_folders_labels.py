import json
import pytest

from tests.util.base import (add_fake_message, thread, add_fake_thread,
                             generic_account, gmail_account)
from tests.api.base import api_client, new_api_client


__all__ = ['api_client', 'thread', 'generic_account', 'gmail_account']


@pytest.fixture
def folder_client(db, generic_account):
    api_client = new_api_client(db, generic_account.namespace)

    api_client.post_data('/folders/',
                         {"display_name": "Test_Folder"})
    return api_client


@pytest.fixture
def label_client(db, gmail_account):
    api_client = new_api_client(db, gmail_account.namespace)

    # Whereas calling generic_account always makes a new IMAP account,
    # calling gmail_account checks first to see if there's an existing
    # Gmail account and uses it if so. This can cause namespace
    # conflicts if a label is "created" more than once. Since
    # labels can't be deleted and then re-created, this fixture only
    # makes a new label if there are no existing labels.
    g_data = api_client.get_raw('/labels/')
    if not json.loads(g_data.data):
        api_client.post_data('/labels/',
                             {"display_name": "Test_Label"})
    return api_client


def test_folder_post(db, generic_account):
    api_client = new_api_client(db, generic_account.namespace)
    po_data = api_client.post_data('/folders/',
                                   {"display_name": "Test_Folder"})
    assert po_data.status_code == 200


def test_label_post(db, gmail_account):
    api_client = new_api_client(db, gmail_account.namespace)
    po_data = api_client.post_data('/labels/',
                                   {"display_name": "Test_Label"})
    assert po_data.status_code == 200


def test_folder_get(folder_client):
    g_data = folder_client.get_raw('/folders/')
    assert g_data.status_code == 200

    gen_folder = json.loads(g_data.data)[0]
    gid_data = folder_client.get_raw('/folders/{}'.format(gen_folder['id']))
    assert gid_data.status_code == 200


def test_label_get(label_client):
    g_data = label_client.get_raw('/labels/')
    assert g_data.status_code == 200

    gmail_label = json.loads(g_data.data)[0]
    gid_data = label_client.get_raw('/labels/{}'.format(gmail_label['id']))
    assert gid_data.status_code == 200


def test_folder_put(folder_client):
    # GET request for the folder ID
    g_data = folder_client.get_raw('/folders/')
    gen_folder = json.loads(g_data.data)[0]

    pu_data = folder_client.put_data('/folders/{}'.format(gen_folder['id']),
                                     {"display_name": "Test_Folder_Renamed"})
    assert pu_data.status_code == 200
    assert json.loads(pu_data.data)['display_name'] == 'Test_Folder_Renamed'


def test_label_put(label_client):
    # GET request for the label ID
    g_data = label_client.get_raw('/labels/')
    gmail_label = json.loads(g_data.data)[0]

    pu_data = label_client.put_data('/labels/{}'.format(gmail_label['id']),
                                    {"display_name": "Test_Label_Renamed"})
    assert pu_data.status_code == 200
    assert json.loads(pu_data.data)['display_name'] == 'Test_Label_Renamed'


def test_folder_delete(db, generic_account, folder_client):
    # Make a new message
    generic_thread = add_fake_thread(db.session, generic_account.namespace.id)
    gen_message = add_fake_message(db.session,
                                   generic_account.namespace.id,
                                   generic_thread)
    g_data = folder_client.get_raw('/folders/')
    # Add message to folder
    generic_folder = json.loads(g_data.data)[0]
    data = {"folder_id": generic_folder['id']}
    folder_client.put_data('/messages/{}'.format(gen_message.public_id), data)

    # Test that DELETE requests 403 on folders with items in them
    d_data = folder_client.delete('/folders/{}'.format(generic_folder['id']))
    assert d_data.status_code == 403

    # Make an empty folder
    resp = folder_client.post_data('/folders/',
                                   {"display_name": "Empty_Folder"})
    empty_folder = json.loads(resp.data)
    # Test that DELETE requests delete empty folders
    d_data = folder_client.delete('/folders/{}'.format(empty_folder['id']))
    assert d_data.status_code == 200


def test_label_delete(db, gmail_account, label_client):
    # Make a new message
    gmail_thread = add_fake_thread(db.session, gmail_account.namespace.id)
    gmail_message = add_fake_message(db.session,
                                     gmail_account.namespace.id, gmail_thread)
    g_data = label_client.get_raw('/labels/')
    # Add label to message
    gmail_label = json.loads(g_data.data)[0]
    data = {"folder_id": gmail_label['id']}
    label_client.put_data('/messages/{}'.format(gmail_message.public_id), data)

    # DELETE requests should work on labels whether or not messages have them
    d_data = label_client.delete('/labels/{}'.format(gmail_label['id']))
    assert d_data.status_code == 200


def test_folder_exclusivity(folder_client):
    g_data = folder_client.get_raw('/folders/')
    generic_folder = json.loads(g_data.data)[0]
    # These requests to /labels/ should all 404, since the account uses folders
    po_data = folder_client.post_data('/labels/',
                                      {"display_name": "Test_E_Label"})
    assert po_data.status_code == 404
    pu_data = folder_client.put_data('/labels/{}'.format(generic_folder['id']),
                                     {"display_name": "Test_E_Folder_Renamed"})
    assert pu_data.status_code == 404
    g_data = folder_client.get_raw('/labels/')
    assert g_data.status_code == 404
    gid_data = folder_client.get_raw('/labels/{}'.format(generic_folder['id']))
    assert gid_data.status_code == 404
    d_data = folder_client.delete('/labels/{}'.format(generic_folder['id']))
    assert d_data.status_code == 404


def test_label_exclusivity(label_client):
    g_data = label_client.get_raw('/labels/')
    gmail_label = json.loads(g_data.data)[0]
    # These requests to /folders/ should all 404, since the account uses labels
    po_data = label_client.post_data('/folders/',
                                     {"display_name": "Test_E_Folder"})
    assert po_data.status_code == 404
    pu_data = label_client.put_data('/folders/{}'.format(gmail_label['id']),
                                    {"display_name": "Test_E _Label_Renamed"})
    assert pu_data.status_code == 404
    g_data = label_client.get_raw('/folders/')
    assert g_data.status_code == 404
    gid_data = label_client.get_raw('/folders/{}'.format(gmail_label['id']))
    assert gid_data.status_code == 404
    d_data = label_client.delete('/folders/{}'.format(gmail_label['id']))
    assert d_data.status_code == 404
