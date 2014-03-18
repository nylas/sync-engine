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
