"""
Sanity-check our logic for updating contact data from message addressees
during a sync.

"""
from datetime import datetime
from inbox.models import Message, Thread, Contact
from inbox.contacts.process_mail import update_contacts_from_message

NAMESPACE_ID = 1


def add_fake_message(db_session, thread, from_addr=None, to_addr=None,
                     cc_addr=None, bcc_addr=None):
    m = Message()
    m.from_addr = from_addr or []
    m.to_addr = to_addr or []
    m.cc_addr = cc_addr or []
    m.bcc_addr = bcc_addr or []
    m.received_date = datetime.utcnow()
    m.size = 0
    m.sanitized_body = ''
    m.snippet = ''
    m.thread = thread
    account_id = thread.namespace.account_id
    update_contacts_from_message(db_session, m, account_id)
    db_session.add(m)
    db_session.commit()
    return m


def test_update_contacts_from_message(db):
    thread = db.session.query(Thread).filter_by(
        namespace_id=NAMESPACE_ID).first()
    # Check that only one Contact is created for repeatedly-referenced
    # addresses.
    add_fake_message(db.session, thread,
                     from_addr=[('', 'alpha@example.com')],
                     cc_addr=[('', 'alpha@example.com')])

    assert db.session.query(Contact).filter_by(
        email_address='alpha@example.com').count() == 1

    # Check that existing Contacts are used when we process a new message
    # referencing them.
    add_fake_message(db.session, thread,
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
    msg = add_fake_message(db.session, thread,
                           from_addr=[('', 'alpha.beta@gmail.com')],
                           cc_addr=[('', 'alphabeta@gmail.com')])

    # Because Gmail addresses with and without periods are the same, check that
    # there are two MessageContactAssociation instances attached to the message
    # (one for the from field, one for the cc field), but that that they
    # reference the same contact.
    assert len(msg.contacts) == 2
    assert len(set(association.contact for association in msg.contacts)) == 1
