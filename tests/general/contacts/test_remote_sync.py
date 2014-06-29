import pytest

from tests.util.base import config
# Need to set up test config before we can import from
# inbox.models.tables.
config()
from inbox.models import Contact
from inbox.contacts.remote_sync import merge, poll, MergeError

ACCOUNT_ID = 1


# STOPSHIP(emfree): Test multiple distinct remote providers

class ContactsProviderStub(object):
    """Contacts provider stub to stand in for an actual provider.
    When an instance's get_contacts() method is called, return an iterable of
    Contact objects corresponding to the data it's been fed via
    supply_contact().
    """
    def __init__(self, provider_name='test_provider'):
        self._contacts = []
        self._next_uid = 1
        self.PROVIDER_NAME = provider_name

    def supply_contact(self, name, email_address, deleted=False):
        self._contacts.append(Contact(account_id=ACCOUNT_ID,
                                      uid=str(self._next_uid),
                                      source='remote',
                                      provider_name=self.PROVIDER_NAME,
                                      name=name,
                                      email_address=email_address,
                                      deleted=deleted))
        self._next_uid += 1

    def get_contacts(self, *args, **kwargs):
        return self._contacts


@pytest.fixture(scope='function')
def contacts_provider(config, db):
    return ContactsProviderStub()


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
    merge(base, remote, dest)
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
        merge(base, remote, dest)

    # Check no update in case of conflict
    assert dest.name == 'Some Other Name'
    assert dest.email_address == 'newaddress@inboxapp.com'


def test_add_contacts(contacts_provider, db):
    """Test that added contacts get stored."""
    num_original_local_contacts = db.session.query(Contact). \
        filter_by(account_id=ACCOUNT_ID).filter_by(source='local').count()
    num_original_remote_contacts = db.session.query(Contact). \
        filter_by(account_id=ACCOUNT_ID).filter_by(source='remote').count()
    contacts_provider.supply_contact('Contact One',
                                     'contact.one@email.address')
    contacts_provider.supply_contact('Contact Two',
                                     'contact.two@email.address')

    poll(ACCOUNT_ID, contacts_provider)
    num_current_local_contacts = db.session.query(Contact). \
        filter_by(account_id=ACCOUNT_ID).filter_by(source='local').count()
    num_current_remote_contacts = db.session.query(Contact). \
        filter_by(account_id=ACCOUNT_ID).filter_by(source='remote').count()
    assert num_current_local_contacts - num_original_local_contacts == 2
    assert num_current_remote_contacts - num_original_remote_contacts == 2


def test_update_contact(contacts_provider, db):
    """Test that subsequent contact updates get stored."""
    contacts_provider.supply_contact('Old Name', 'old@email.address')
    poll(ACCOUNT_ID, contacts_provider)
    results = db.session.query(Contact).filter_by(source='remote').all()
    db.new_session()
    email_addresses = [r.email_address for r in results]
    assert 'old@email.address' in email_addresses

    contacts_provider.__init__()
    contacts_provider.supply_contact('New Name', 'new@email.address')
    poll(ACCOUNT_ID, contacts_provider)
    results = db.session.query(Contact).filter_by(source='remote').all()
    names = [r.name for r in results]
    assert 'New Name' in names
    email_addresses = [r.email_address for r in results]
    assert 'new@email.address' in email_addresses


def test_uses_local_updates(contacts_provider, db):
    """Test that non-conflicting local and remote updates to the same contact
    both get stored."""
    contacts_provider.supply_contact('Old Name', 'old@email.address')
    poll(ACCOUNT_ID, contacts_provider)
    results = db.session.query(Contact).filter_by(source='local').all()
    # Fake a local contact update.
    results[-1].name = 'New Name'
    db.session.commit()

    contacts_provider.__init__()
    contacts_provider.supply_contact('Old Name', 'new@email.address')
    poll(ACCOUNT_ID, contacts_provider)

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


def test_multiple_remotes(contacts_provider, alternate_contacts_provider, db):
    contacts_provider.supply_contact('Name', 'name@email.address')
    alternate_contacts_provider.supply_contact('Alternate Name',
                                               'name@email.address')

    poll(ACCOUNT_ID, contacts_provider)
    poll(ACCOUNT_ID, alternate_contacts_provider)
    result = db.session.query(Contact). \
        filter_by(source='local', provider_name='test_provider').one()
    alternate_result = db.session.query(Contact). \
        filter_by(source='local', provider_name='alternate_provider').one()
    # Check that both contacts were persisted, even though they have the same
    # uid.
    assert result.name == 'Name'
    assert alternate_result.name == 'Alternate Name'


def test_deletes(contacts_provider, db):
    num_original_contacts = db.session.query(Contact).count()
    contacts_provider.supply_contact('Name', 'name@email.address')
    poll(ACCOUNT_ID, contacts_provider)
    num_current_contacts = db.session.query(Contact).count()
    assert num_current_contacts - num_original_contacts == 2

    contacts_provider.__init__()
    contacts_provider.supply_contact(None, None, deleted=True)
    poll(ACCOUNT_ID, contacts_provider)
    num_current_contacts = db.session.query(Contact).count()
    assert num_current_contacts == num_original_contacts
