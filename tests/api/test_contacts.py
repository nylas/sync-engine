import json

from inbox.models import Account
from tests.util.base import (contact_sync, contacts_provider,
                             api_client)

__all__ = ['contacts_provider', 'contact_sync', 'api_client']


ACCOUNT_ID = 1


def test_api_list(contacts_provider, contact_sync, db, api_client):
    contacts_provider.supply_contact('Contact One',
                                     'contact.one@email.address')
    contacts_provider.supply_contact('Contact Two',
                                     'contact.two@email.address')

    contact_sync.provider_instance = contacts_provider
    contact_sync.poll()
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    contact_list = api_client.get_data('/contacts', ns_id)
    contact_names = [contact['name'] for contact in contact_list]
    assert 'Contact One' in contact_names
    assert 'Contact Two' in contact_names

    contact_emails = [contact['email'] for contact in contact_list]
    assert 'contact.one@email.address' in contact_emails
    assert 'contact.two@email.address' in contact_emails


def test_api_get(contacts_provider, contact_sync, db, api_client):
    contacts_provider.supply_contact('Contact One',
                                     'contact.one@email.address')
    contacts_provider.supply_contact('Contact Two',
                                     'contact.two@email.address')

    contact_sync.provider_instance = contacts_provider
    contact_sync.poll()
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    contact_list = api_client.get_data('/contacts', ns_id)

    contact_ids = [contact['id'] for contact in contact_list]

    c1found = False
    c2found = False
    for c_id in contact_ids:
        contact = api_client.get_data('/contacts/' + c_id, ns_id)

        if contact['name'] == 'Contact One':
            c1found = True

        if contact['name'] == 'Contact Two':
            c2found = True

    assert c1found
    assert c2found


def test_api_create(contacts_provider, contact_sync, db, api_client):
    acct = db.session.query(Account).filter_by(id=ACCOUNT_ID).one()
    ns_id = acct.namespace.public_id

    c_data = {
        'name': 'Contact One',
        'email': 'contact.one@email.address'
    }

    c_resp = api_client.post_data('/contacts', c_data, ns_id)
    c_resp_data = json.loads(c_resp.data)
    assert c_resp_data['object'] == 'contact'
    assert c_resp_data['namespace_id'] == acct.namespace.public_id
    assert c_resp_data['email'] == c_data['email']
    assert c_resp_data['name'] == c_data['name']
    assert 'id' in c_resp_data
    c_id = c_resp_data['id']
    c_get_resp = api_client.get_data('/contacts/' + c_id, ns_id)

    assert c_get_resp['object'] == 'contact'
    assert c_get_resp['namespace_id'] == acct.namespace.public_id
    assert c_get_resp['email'] == c_data['email']
    assert c_get_resp['name'] == c_data['name']
    assert c_get_resp['id'] == c_id
