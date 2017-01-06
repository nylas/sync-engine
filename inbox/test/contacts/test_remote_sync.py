import pytest

from inbox.test.util.base import (contact_sync, contacts_provider,
                                  ContactsProviderStub)

from inbox.models import Contact

__all__ = ['contact_sync', 'contacts_provider']


@pytest.fixture(scope='function')
def alternate_contacts_provider():
    return ContactsProviderStub('alternate_provider')


def test_add_contacts_case_insensitive(contacts_provider, contact_sync, db, default_namespace):
    """Tests that syncing two contacts with uids that differ only in case sensitivity doesn't cause an error."""
    num_original_contacts = db.session.query(Contact). \
        filter_by(namespace_id=default_namespace.id).count()
    contacts_provider._next_uid = 'foo'
    contacts_provider._get_next_uid = lambda current: 'FOO'
    contacts_provider.supply_contact('Contact One',
                                     'contact.one@email.address')
    contacts_provider.supply_contact('Contact Two',
                                     'contact.two@email.address')
    contact_sync.provider = contacts_provider
    contact_sync.sync()
    num_current_contacts = db.session.query(Contact). \
        filter_by(namespace_id=default_namespace.id).count()
    assert num_current_contacts - num_original_contacts == 2


def test_add_contacts(contacts_provider, contact_sync, db, default_namespace):
    """Test that added contacts get stored."""
    num_original_contacts = db.session.query(Contact). \
        filter_by(namespace_id=default_namespace.id).count()
    contacts_provider.supply_contact('Contact One',
                                     'contact.one@email.address')
    contacts_provider.supply_contact('Contact Two',
                                     'contact.two@email.address')

    contact_sync.provider = contacts_provider
    contact_sync.sync()
    num_current_contacts = db.session.query(Contact). \
        filter_by(namespace_id=default_namespace.id).count()
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


def test_auth_error_handling(contact_sync, default_account, db):
    """Test that the contact sync greenlet stops if account credentials are
    invalid."""
    # Give the default test account patently invalid OAuth credentials.
    default_account.refresh_token = 'foo'
    for auth_creds in default_account.auth_credentials:
        auth_creds.refresh_token = 'foo'
    db.session.commit()

    contact_sync.start()
    contact_sync.join(timeout=10)
    success = contact_sync.successful()
    if not success:
        contact_sync.kill()
    assert success, "contact sync greenlet didn't terminate."
