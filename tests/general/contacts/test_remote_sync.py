import pytest

from tests.util.base import config
from tests.util.base import (contact_sync, contacts_provider, default_account,
                             ContactsProviderStub)

# Need to set up test config before we can import from
# inbox.models.tables.
config()
from inbox.models import Contact
from inbox.util.misc import MergeError

__all__ = ['contact_sync', 'contacts_provider']

NAMESPACE_ID = 1

# STOPSHIP(emfree): Test multiple distinct remote providers


@pytest.fixture(scope='function')
def alternate_contacts_provider(config, db):
    return ContactsProviderStub('alternate_provider')


def test_merge(config):
    """Test the basic logic of the merge() function."""
    base = Contact(name='Original Name',
                   email_address='originaladdress@inboxapp.com')
    remote = Contact(name='New Name',
                     email_address='originaladdress@inboxapp.com')
    dest = Contact(name='Original Name',
                   email_address='newaddress@inboxapp.com')
    dest.merge_from(base, remote)
    assert dest.name == 'New Name'
    assert dest.email_address == 'newaddress@inboxapp.com'


def test_merge_conflict(config):
    """Test that merge() raises an error on conflict."""
    base = Contact(name='Original Name',
                   email_address='originaladdress@inboxapp.com')
    remote = Contact(name='New Name',
                     email_address='originaladdress@inboxapp.com')
    dest = Contact(name='Some Other Name',
                   email_address='newaddress@inboxapp.com')
    with pytest.raises(MergeError):
        dest.merge_from(base, remote)

    # Check no update in case of conflict
    assert dest.name == 'Some Other Name'
    assert dest.email_address == 'newaddress@inboxapp.com'


def test_add_contacts(contacts_provider, contact_sync, db):
    """Test that added contacts get stored."""
    num_original_local_contacts = db.session.query(Contact). \
        filter_by(namespace_id=NAMESPACE_ID).filter_by(source='local').count()
    num_original_remote_contacts = db.session.query(Contact). \
        filter_by(namespace_id=NAMESPACE_ID).filter_by(source='remote').count()
    contacts_provider.supply_contact('Contact One',
                                     'contact.one@email.address')
    contacts_provider.supply_contact('Contact Two',
                                     'contact.two@email.address')

    contact_sync.provider_instance = contacts_provider
    contact_sync.poll()
    num_current_local_contacts = db.session.query(Contact). \
        filter_by(namespace_id=NAMESPACE_ID).filter_by(source='local').count()
    num_current_remote_contacts = db.session.query(Contact). \
        filter_by(namespace_id=NAMESPACE_ID).filter_by(source='remote').count()
    assert num_current_local_contacts - num_original_local_contacts == 2
    assert num_current_remote_contacts - num_original_remote_contacts == 2


def test_update_contact(contacts_provider, contact_sync, db):
    """Test that subsequent contact updates get stored."""
    contacts_provider.supply_contact('Old Name', 'old@email.address')
    contact_sync.provider_instance = contacts_provider
    contact_sync.poll()
    results = db.session.query(Contact).filter_by(source='remote').all()
    db.new_session()
    email_addresses = [r.email_address for r in results]
    assert 'old@email.address' in email_addresses

    contacts_provider.__init__()
    contacts_provider.supply_contact('New Name', 'new@email.address')
    contact_sync.poll()
    db.new_session()

    results = db.session.query(Contact).filter_by(source='remote').all()
    names = [r.name for r in results]
    assert 'New Name' in names
    email_addresses = [r.email_address for r in results]
    assert 'new@email.address' in email_addresses


def test_uses_local_updates(contacts_provider, contact_sync, db):
    """Test that non-conflicting local and remote updates to the same contact
    both get stored."""
    contacts_provider.supply_contact('Old Name', 'old@email.address')
    contact_sync.provider_instance = contacts_provider
    contact_sync.poll()
    results = db.session.query(Contact).filter_by(source='local').all()
    # Fake a local contact update.
    results[-1].name = 'New Name'
    db.session.commit()

    contacts_provider.__init__()
    contacts_provider.supply_contact('Old Name', 'new@email.address')
    contact_sync.provider_instance = contacts_provider
    contact_sync.poll()

    remote_results = db.session.query(Contact).filter_by(source='remote').all()
    names = [r.name for r in remote_results]
    assert 'New Name' in names
    email_addresses = [r.email_address for r in remote_results]
    assert 'new@email.address' in email_addresses

    local_results = db.session.query(Contact).filter_by(source='local').all()
    names = [r.name for r in local_results]
    assert 'New Name' in names
    email_addresses = [r.email_address for r in local_results]
    assert 'new@email.address' in email_addresses


def test_multiple_remotes(contacts_provider, alternate_contacts_provider,
                          contact_sync, db):
    contacts_provider.supply_contact('Name', 'name@email.address')
    alternate_contacts_provider.supply_contact('Alternate Name',
                                               'name@email.address')

    contact_sync.provider_instance = contacts_provider
    contact_sync.poll()

    contact_sync.provider_instance = alternate_contacts_provider
    contact_sync.poll()

    result = db.session.query(Contact). \
        filter_by(source='local', provider_name='test_provider').one()
    alternate_result = db.session.query(Contact). \
        filter_by(source='local', provider_name='alternate_provider').one()
    # Check that both contacts were persisted, even though they have the same
    # uid.
    assert result.name == 'Name'
    assert alternate_result.name == 'Alternate Name'


def test_deletes(contacts_provider, contact_sync, db):
    num_original_contacts = db.session.query(Contact).count()
    contacts_provider.supply_contact('Name', 'name@email.address')
    contact_sync.provider_instance = contacts_provider
    contact_sync.poll()
    num_current_contacts = db.session.query(Contact).count()
    assert num_current_contacts - num_original_contacts == 2

    contacts_provider.__init__()
    contacts_provider.supply_contact(None, None, deleted=True)
    contact_sync.poll()

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
