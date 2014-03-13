from pytest import fixture

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
        from inbox.server.models.tables import Contact
        self._contacts.append(Contact(imapaccount_id=ACCOUNT_ID,
                                      g_id=str(self._next_g_id),
                                      source='remote',
                                      name=name,
                                      email_address=email_address))
        self._next_g_id += 1

    def get_contacts(self, *args, **kwargs):
        return self._contacts


@fixture(scope='function')
def contacts_provider(config, db):
    return ContactsProviderStub()
