from inbox.models import Contact
from inbox.test.util.base import contact_sync, contacts_provider
from inbox.test.api.base import api_client

__all__ = ['contacts_provider', 'contact_sync', 'api_client']


def test_api_list(contacts_provider, contact_sync, db, api_client,
                  default_namespace):
    contacts_provider.supply_contact('Contact One',
                                     'contact.one@email.address')
    contacts_provider.supply_contact('Contact Two',
                                     'contact.two@email.address')

    contact_sync.provider = contacts_provider
    contact_sync.sync()

    contact_list = api_client.get_data('/contacts')
    contact_names = [contact['name'] for contact in contact_list]
    assert 'Contact One' in contact_names
    assert 'Contact Two' in contact_names

    contact_emails = [contact['email'] for contact in contact_list]
    assert 'contact.one@email.address' in contact_emails
    assert 'contact.two@email.address' in contact_emails

    contact_count = api_client.get_data('/contacts?view=count')
    assert contact_count['count'] == db.session.query(Contact). \
        filter(Contact.namespace_id == default_namespace.id).count()


def test_api_get(contacts_provider, contact_sync, db, api_client,
                 default_namespace):
    contacts_provider.supply_contact('Contact One',
                                     'contact.one@email.address')
    contacts_provider.supply_contact('Contact Two',
                                     'contact.two@email.address')

    contact_sync.provider = contacts_provider
    contact_sync.sync()

    contact_list = api_client.get_data('/contacts')

    contact_ids = [contact['id'] for contact in contact_list]

    c1found = False
    c2found = False
    for c_id in contact_ids:
        contact = api_client.get_data('/contacts/' + c_id)

        if contact['name'] == 'Contact One':
            c1found = True

        if contact['name'] == 'Contact Two':
            c2found = True

    assert c1found
    assert c2found
