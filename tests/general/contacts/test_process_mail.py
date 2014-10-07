"""Sanity-check our logic for updating contact data from message addressees
during a sync."""
from inbox.models import Thread, Contact
from tests.util.base import add_fake_message

NAMESPACE_ID = 1


def test_update_contacts_from_message(db):
    thread = db.session.query(Thread).filter_by(
        namespace_id=NAMESPACE_ID).first()
    # Check that only one Contact is created for repeatedly-referenced
    # addresses.
    add_fake_message(db.session, NAMESPACE_ID, thread,
                     from_addr=[('', 'alpha@example.com')],
                     cc_addr=[('', 'alpha@example.com')])

    assert db.session.query(Contact).filter_by(
        email_address='alpha@example.com').count() == 1

    # Check that existing Contacts are used when we process a new message
    # referencing them.
    add_fake_message(db.session, NAMESPACE_ID, thread,
                     from_addr=[('', 'alpha@example.com')],
                     cc_addr=[('', 'alpha@example.com')],
                     to_addr=[('', 'beta@example.com'),
                              ('', 'gamma@example.com')])

    assert db.session.query(Contact).filter(
        Contact.email_address.like('%@example.com')).count() == 3
    alpha = db.session.query(Contact).filter_by(
        email_address='alpha@example.com').one()
    assert len(alpha.message_associations) == 4


def test_addresses_canonicalized(db):
    thread = db.session.query(Thread).filter_by(
        namespace_id=NAMESPACE_ID).first()
    msg = add_fake_message(db.session, NAMESPACE_ID, thread,
                           from_addr=[('', 'alpha.beta@gmail.com')],
                           cc_addr=[('', 'alphabeta@gmail.com')])

    # Because Gmail addresses with and without periods are the same, check that
    # there are two MessageContactAssociation instances attached to the message
    # (one for the from field, one for the cc field), but that that they
    # reference the same contact.
    assert len(msg.contacts) == 2
    assert len(set(association.contact for association in msg.contacts)) == 1
