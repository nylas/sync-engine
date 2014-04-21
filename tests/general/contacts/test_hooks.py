import pytest

from tests.util.base import config
config()

from inbox.server.mailsync.hooks import default_hook_manager
from inbox.server.models.tables.base import Contact, Message, register_backends
register_backends()

ACCOUNT_ID = 1


@pytest.fixture
def message():
    return Message(from_addr=('Some Dude', 'some.dude@email.address'),
                   to_addr=(('Somebody Else', 'somebody.else@email.address'),),
                   cc_addr=(('A Bystander', 'bystander@email.address'),),
                   bcc_addr=(('The NSA', 'spies@nsa.gov'),))


def test_contact_hooks(config, message, db):
    default_hook_manager.execute_hooks(ACCOUNT_ID, message)
    contacts = db.session.query(Contact)
    assert contacts.count() == 4
