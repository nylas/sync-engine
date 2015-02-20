import pytest

from tests.util.base import (contact_sync, contacts_provider, default_account,
                             ContactsProviderStub)

from inbox.models import Contact

__all__ = ['contact_sync', 'contacts_provider']

NAMESPACE_ID = 1


@pytest.fixture(scope='function')
def alternate_contacts_provider():
    return ContactsProviderStub('alternate_provider')


def test_add_contacts(contacts_provider, contact_sync, db):
    """Test that added contacts get stored."""
    num_original_contacts = db.session.query(Contact). \
        filter_by(namespace_id=NAMESPACE_ID).count()
    contacts_provider.supply_contact('Contact One',
                                     'contact.one@email.address')
    contacts_provider.supply_contact('Contact Two',
                                     'contact.two@email.address')

    contact_sync.provider = contacts_provider
    contact_sync.sync()
    num_current_contacts = db.session.query(Contact). \
        filter_by(namespace_id=NAMESPACE_ID).count()
    assert num_current_contacts - num_original_contacts == 2


def test_update_contact(contacts_provider, contact_sync, db):
    """Test that subsequent contact updates get stored."""
    contacts_provider.supply_contact('Old Name', 'old@email.address')
    contact_sync.provider = contacts_provider
    contact_sync.sync()
    results = db.session.query(Contact).all()
    email_addresses = [r.email_address for r in results]
    assert 'old@email.address' in email_addresses

    contacts_provider.__init__()
    contacts_provider.supply_contact('New Name', 'new@email.address')
    contact_sync.sync()
    db.session.commit()

    results = db.session.query(Contact).all()
    names = [r.name for r in results]
    assert 'New Name' in names
    email_addresses = [r.email_address for r in results]
    assert 'new@email.address' in email_addresses


def test_multiple_remotes(contacts_provider, alternate_contacts_provider,
                          contact_sync, db):
    contacts_provider.supply_contact('Name', 'name@email.address')
    alternate_contacts_provider.supply_contact('Alternate Name',
                                               'name@email.address')

    contact_sync.provider = contacts_provider
    contact_sync.sync()

    contact_sync.provider = alternate_contacts_provider
    contact_sync.sync()

    result = db.session.query(Contact). \
        filter_by(provider_name='test_provider').one()
    alternate_result = db.session.query(Contact). \
        filter_by(provider_name='alternate_provider').one()
    # Check that both contacts were persisted, even though they have the same
    # uid.
    assert result.name == 'Name'
    assert alternate_result.name == 'Alternate Name'


def test_deletes(contacts_provider, contact_sync, db):
    num_original_contacts = db.session.query(Contact).count()
    contacts_provider.supply_contact('Name', 'name@email.address')
    contact_sync.provider = contacts_provider
    contact_sync.sync()
    num_current_contacts = db.session.query(Contact).count()
    assert num_current_contacts - num_original_contacts == 1

    contacts_provider.__init__()
    contacts_provider.supply_contact(None, None, deleted=True)
    contact_sync.sync()

    num_current_contacts = db.session.query(Contact).count()
    assert num_current_contacts == num_original_contacts


def test_auth_error_handling(contact_sync, db):
    """Test that the contact sync greenlet stops if account credentials are
    invalid."""
    # Give the default test account patently invalid OAuth credentials.
    default_account.refresh_token = 'foo'
    db.session.commit()

    contact_sync.start()
    contact_sync.join(timeout=5)
    assert contact_sync.successful(), "contact sync greenlet didn't terminate."
