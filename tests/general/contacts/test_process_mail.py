import datetime
import pytest

from tests.util.base import config
config()

from inbox.contacts.process_mail import update_contacts
from inbox.models.tables.base import Contact, Message, register_backends
register_backends()

ACCOUNT_ID = 1


@pytest.fixture
def message():
    received_date = datetime.datetime.utcfromtimestamp(10**9 + 1)
    return Message(from_addr=(('Some Dude', 'some.dude@email.address'),),
                   to_addr=(('Somebody Else',
                             'somebody.else@email.address'),),
                   cc_addr=(('A Bystander',
                             'bystander@email.address'),),
                   bcc_addr=(('The NSA', 'spies@nsa.gov'),),
                   thread_id=1,
                   size=22,
                   is_draft=False,
                   decode_error=False,
                   sanitized_body='Are you there?',
                   snippet='Are you there?',
                   received_date=received_date)


@pytest.fixture
def gmail_message():
    received_date = datetime.datetime.utcfromtimestamp(10**9 + 1)
    return Message(to_addr=((u'Somebody', u'some.body@gmail.com'),
                            (u'Somebody', u'somebody@gmail.com'),),
                   thread_id=1,
                   size=22,
                   is_draft=False,
                   decode_error=False,
                   sanitized_body='Are you there?',
                   snippet='Are you there?',
                   received_date=received_date)


def test_canonicalization(config, gmail_message, db):
    # STOPSHIP(emfree) doesn't actually test anything
    update_contacts(db.session, ACCOUNT_ID, gmail_message)
    contacts = db.session.query(Contact).filter(Contact.name == 'Somebody')
    assert contacts.count() == 1


def test_contact_update(config, message, db):
    update_contacts(db.session, ACCOUNT_ID, message)
    assert len(message.contacts) == 4
    to_contacts = [assoc.contact for assoc in message.contacts
                   if assoc.field == 'to_addr']
    assert len(to_contacts) == 1
    c = to_contacts[0]
    messages_to = [assoc.message for assoc in c.message_associations
                   if assoc.field == 'to_addr']
    assert len(messages_to) == 1


def test_scoring(config, message, db):
    for _ in range(10):
        # Pretend to process a number of messages.
        update_contacts(db.session, ACCOUNT_ID, message)
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
