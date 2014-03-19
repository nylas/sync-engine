import pytest

from ..util.base import config
# Need to set up test config before we can import from
# inbox.server.models.tables.
config()
from inbox.server.models.tables.base import Contact
from inbox.server.contacts.remote_sync import merge, poll, MergeError

ACCOUNT_ID = 1


class ContactsProviderStub(object):
    """Contacts provider stub to stand in for an actual provider.
    When an instance's get_contacts() method is called, return an iterable of
    Contact objects corresponding to the data it's been fed via
    supply_contact().
    """
    def __init__(self):
        self._contacts = []
        self._next_g_id = 1

    def supply_contact(self, name, email_address):
        self._contacts.append(Contact(account_id=ACCOUNT_ID,
                                      g_id=str(self._next_g_id),
                                      source='remote',
                                      name=name,
                                      email_address=email_address))
        self._next_g_id += 1

    def get_contacts(self, *args, **kwargs):
        return self._contacts


@pytest.fixture(scope='function')
def contacts_provider(config, db):
    return ContactsProviderStub()

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
    contacts_provider.supply_contact('Contact One', 'contact.one@email.address')
    contacts_provider.supply_contact('Contact Two', 'contact.two@email.address')

    poll(ACCOUNT_ID, contacts_provider)
    local_contacts = db.session.query(Contact). \
        filter_by(account_id=ACCOUNT_ID).filter_by(source='local').count()
    remote_contacts = db.session.query(Contact). \
        filter_by(account_id=ACCOUNT_ID).filter_by(source='remote').count()
    assert local_contacts == 2
    assert remote_contacts == 2


def test_update_contact(contacts_provider, db):
    """Test that subsequent contact updates get stored."""
    contacts_provider.supply_contact('Old Name', 'old@email.address')
    poll(ACCOUNT_ID, contacts_provider)
    result = db.session.query(Contact).filter_by(source='remote').one()

    db.new_session()
    assert result.email_address == 'old@email.address'
    contacts_provider.__init__()
    contacts_provider.supply_contact('New Name', 'new@email.address')
    poll(ACCOUNT_ID, contacts_provider)
    result = db.session.query(Contact).filter_by(source='remote').one()
    assert result.name == 'New Name'
    assert result.email_address == 'new@email.address'


def test_uses_local_updates(contacts_provider, db):
    """Test that non-conflicting local and remote updates to the same contact
    both get stored."""
    contacts_provider.supply_contact('Old Name', 'old@email.address')
    poll(ACCOUNT_ID, contacts_provider)
    result = db.session.query(Contact).filter_by(source='local').one()
    # Fake a local contact update.
    result.name = 'New Name'
    db.session.commit()

    db.new_session()
    contacts_provider.__init__()
    contacts_provider.supply_contact('Old Name', 'new@email.address')
    poll(ACCOUNT_ID, contacts_provider)

    db.new_session()
    remote_result = db.session.query(Contact).filter_by(source='remote').one()
    assert remote_result.name == 'New Name'
    assert remote_result.email_address == 'new@email.address'
    local_result = db.session.query(Contact).filter_by(source='local').one()
    assert local_result.name == 'New Name'
    assert local_result.email_address == 'new@email.address'
