import pytest
import datetime

from tests.util.base import config
config()

from inbox.server.mailsync.hooks import default_hook_manager
from inbox.server.models.tables.base import Contact, Message, register_backends
register_backends()

ACCOUNT_ID = 1


@pytest.fixture
def message():
    received_date = datetime.datetime.utcfromtimestamp(10**9 + 1)
    return Message(from_addr=('Some Dude', 'some.dude@email.address'),
                   to_addr=(('Somebody Else', 'somebody.else@email.address'),),
                   cc_addr=(('A Bystander', 'bystander@email.address'),),
                   bcc_addr=(('The NSA', 'spies@nsa.gov'),),
                   received_date=received_date)

@pytest.fixture
def gmail_message():
    received_date = datetime.datetime.utcfromtimestamp(10**9 + 1)
    return Message(to_addr=((u'Somebody ', u'some.body@gmail.com'),
                            (u'The same person', u'somebody@gmail.com')),
                   received_date=received_date)


def test_canonicalization(config, gmail_message, db):
    default_hook_manager.execute_hooks(ACCOUNT_ID, gmail_message)
    contacts = db.session.query(Contact)
    assert contacts.count() == 1


def test_contact_hooks(config, message, db):
    default_hook_manager.execute_hooks(ACCOUNT_ID, message)
    contacts = db.session.query(Contact)
    assert contacts.count() == 4


def test_scoring(config, message, db):
    for _ in range(10):
        # Pretend to process a number of messages.
        default_hook_manager.execute_hooks(ACCOUNT_ID, message)
    # The expected scores here must be updated when the scoring function
    # changes.
    contact = db.session.query(Contact). \
        filter(Contact.email_address == 'some.dude@email.address').one()
    assert contact.score == 10
    contact = db.session.query(Contact). \
        filter(Contact.email_address == 'somebody.else@email.address').one()
    assert contact.score == 19
    contact = db.session.query(Contact). \
        filter(Contact.email_address == 'bystander@email.address').one()
    assert contact.score == 10
