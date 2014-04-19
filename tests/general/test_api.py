import json
from bson import json_util

import pytest
from zerorpc.exceptions import RemoteError

# pytest fixtures outside of conftest.py must be imported for discovery
from tests.util.api import api_client
from tests.util.mailsync import sync_client
from tests.data.messages.message import TEST_MSG

USER_ID = 1
NAMESPACE_ID = 1
ACCOUNT_ID = 1
NONEXISTENT_CONTACT_ID = 22222222


def test_sync_status(api_client, sync_client):
    result = api_client.sync_status()
    # TODO(emfree): actually run a sync and test the result
    expected = '{}'
    assert (result == expected)


def test_is_mailing_list_thread(api_client):
    result = api_client.is_mailing_list_thread(USER_ID, NAMESPACE_ID,
                                               TEST_MSG['thread_id'])
    expected = True

    assert (result == expected)


def test_mailing_list_info_for_thread(api_client):
    result = api_client.mailing_list_info_for_thread(USER_ID, NAMESPACE_ID,
                                                     TEST_MSG['thread_id'])
    expected = json.dumps(TEST_MSG['mailing_list_headers'],
                          default=json_util.default)

    assert (result == expected)


def test_headers_for_message(api_client):
    result = api_client.headers_for_message(USER_ID, NAMESPACE_ID,
                                            TEST_MSG['msg_id'])
    expected = TEST_MSG['all_headers']

    assert (result == expected)


def test_add_get_contact(api_client):
    example_contact_data = {'name': 'New Contact',
                            'email': 'new.contact@email.address'}
    contact_id = api_client.add_contact(ACCOUNT_ID, example_contact_data)
    result = api_client.get_contact(contact_id)
    assert result['name'] == example_contact_data['name']
    assert result['email'] == example_contact_data['email']


def test_add_update_contacte(api_client):
    example_contact_data = {'name': 'New Contact',
                            'email': 'new.contact@email.address'}
    contact_id = api_client.add_contact(ACCOUNT_ID, example_contact_data)
    example_contact_data['email'] = 'some.other@email.address'
    api_client.update_contact(contact_id, example_contact_data)
    result = api_client.get_contact(contact_id)
    assert result['name'] == example_contact_data['name']
    assert result['email'] == example_contact_data['email']


def test_error_on_bad_contact_update(api_client):
    with pytest.raises(RemoteError):
        api_client.update_contact(ACCOUNT_ID, NONEXISTENT_CONTACT_ID)


def test_contact_search(api_client):
    """Basic smoke tests for search."""
    search_data = [{'name': 'Some Dude',
                    'email': 'some.dude@email.address'},
                   {'name': 'Some Other Dude',
                    'email': 'some.other.dude@email.address'},
                   {'name': 'Somebody Else',
                    'email': 'somebody.else@email.address'}]
    for contact in search_data:
        api_client.add_contact(ACCOUNT_ID, contact)

    result = api_client.search_contacts(ACCOUNT_ID, 'Some')
    assert len(result) == 3

    result = api_client.search_contacts(ACCOUNT_ID, 'Some', 1)
    assert len(result) == 1

    result = api_client.search_contacts(ACCOUNT_ID, 'Some Other')
    assert len(result) == 1
    assert result[0]['name'] == 'Some Other Dude'
    assert result[0]['email'] == 'some.other.dude@email.address'

    result = api_client.search_contacts(ACCOUNT_ID, 'Other')
    assert len(result) == 1
    assert result[0]['name'] == 'Some Other Dude'
    assert result[0]['email'] == 'some.other.dude@email.address'

    result = api_client.search_contacts(ACCOUNT_ID, 'somebody.else')
    assert len(result) == 1
    assert result[0]['name'] == 'Somebody Else'
    assert result[0]['email'] == 'somebody.else@email.address'


def test_search_missing_fields(api_client):
    api_client.add_contact(ACCOUNT_ID, {'name': 'Some Dude', 'email': None})
    api_client.add_contact(ACCOUNT_ID, {'name': None, 'email': 'someemail'})
    result = api_client.search_contacts(ACCOUNT_ID, 'Some')
    assert len(result) == 2
