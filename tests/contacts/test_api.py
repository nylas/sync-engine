import json

import pytest
from zerorpc.exceptions import RemoteError

from ..util.base import TestZeroRPC, db

ACCOUNT_ID = 1
NONEXISTENT_CONTACT_ID = 22222222


@pytest.fixture(scope='function')
def contact_client(config, db):
    contact_server_loc = config.get('CONTACT_SERVER_LOC', None)
    from inbox.server.contacts.api import ContactService

    test = TestZeroRPC(config, db, ContactService, contact_server_loc)

    return test.client


def test_add_get(contact_client, db):
    example_contact_data = {'name': 'New Contact',
                            'email': 'new.contact@email.address'}
    contact_id = contact_client.add(ACCOUNT_ID, example_contact_data)
    result = json.loads(contact_client.get(contact_id))
    assert result['name'] == example_contact_data['name']
    assert result['email'] == example_contact_data['email']


def test_add_update(contact_client, db):
    example_contact_data = {'name': 'New Contact',
                            'email': 'new.contact@email.address'}
    contact_id = contact_client.add(ACCOUNT_ID, example_contact_data)
    example_contact_data['email'] = 'some.other@email.address'
    contact_client.update(contact_id, example_contact_data)
    result = json.loads(contact_client.get(contact_id))
    assert result['name'] == example_contact_data['name']
    assert result['email'] == example_contact_data['email']


def test_error_on_bad_update(contact_client, db):
    with pytest.raises(RemoteError):
        contact_client.update(ACCOUNT_ID, NONEXISTENT_CONTACT_ID)


def test_search(contact_client, db):
    """Basic smoke tests for search."""
    search_data = [{'name': 'Some Dude',
                    'email': 'some.dude@email.address'},
                   {'name': 'Some Other Dude',
                    'email': 'some.other.dude@email.address'},
                   {'name': 'Somebody Else',
                    'email': 'somebody.else@email.address'}]
    for contact in search_data:
        contact_client.add(ACCOUNT_ID, contact)

    result = json.loads(contact_client.search(ACCOUNT_ID, 'Some'))
    assert len(result) == 3

    result = json.loads(contact_client.search(ACCOUNT_ID, 'Some', 1))
    assert len(result) == 1

    result = json.loads(contact_client.search(ACCOUNT_ID, 'Some Other'))
    assert len(result) == 1
    assert result[0]['name'] == 'Some Other Dude'
    assert result[0]['email'] == 'some.other.dude@email.address'

    result = json.loads(contact_client.search(ACCOUNT_ID, 'Other'))
    assert len(result) == 1
    assert result[0]['name'] == 'Some Other Dude'
    assert result[0]['email'] == 'some.other.dude@email.address'

    result = json.loads(contact_client.search(ACCOUNT_ID, 'somebody.else'))
    assert len(result) == 1
    assert result[0]['name'] == 'Somebody Else'
    assert result[0]['email'] == 'somebody.else@email.address'


def test_search_missing_fields(contact_client, db):
    contact_client.add(ACCOUNT_ID, {'name': 'Some Dude', 'email': None})
    contact_client.add(ACCOUNT_ID, {'name': None, 'email': 'someemail'})
    result = json.loads(contact_client.search(ACCOUNT_ID, 'Some'))
    assert len(result) == 2
