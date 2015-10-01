"""Sanity-check our logic for updating contact data from message addressees
during a sync."""
from inbox.models import Contact
from tests.util.base import add_fake_message


def test_update_contacts_from_message(db, default_namespace, thread):
    # Check that only one Contact is created for repeatedly-referenced
    # addresses.
    add_fake_message(db.session, default_namespace.id, thread,
                     from_addr=[('', 'alpha@example.com')],
                     cc_addr=[('', 'alpha@example.com')])

    assert db.session.query(Contact).filter_by(
        email_address='alpha@example.com').count() == 1

    # Check that existing Contacts are used when we process a new message
    # referencing them.
    add_fake_message(db.session, default_namespace.id, thread,
                     from_addr=[('', 'alpha@example.com')],
                     cc_addr=[('', 'alpha@example.com')],
                     to_addr=[('', 'beta@example.com'),
                              ('', 'gamma@example.com')])

    assert db.session.query(Contact).filter(
        Contact.email_address.like('%@example.com'),
        Contact.namespace_id == default_namespace.id).count() == 3
    alpha = db.session.query(Contact).filter_by(
        email_address='alpha@example.com',
        namespace_id=default_namespace.id).one()
    assert len(alpha.message_associations) == 4


def test_addresses_canonicalized(db, default_namespace, thread):
    msg = add_fake_message(db.session, default_namespace.id, thread,
                           from_addr=[('', 'alpha.beta@gmail.com')],
                           cc_addr=[('', 'alphabeta@gmail.com')],
                           bcc_addr=[('', 'ALPHABETA@GMAIL.COM')])

    # Because Gmail addresses with and without periods are the same, check that
    # there are three MessageContactAssociation instances attached to the
    # message (one each from the from/to/cc fields), but that they reference
    # the same contact.
    assert len(msg.contacts) == 3
    assert len(set(association.contact for association in msg.contacts)) == 1


def test_handle_noreply_addresses(db, default_namespace, thread):
    add_fake_message(
        db.session, default_namespace.id, thread,
        from_addr=[('Alice', 'drive-shares-noreply@google.com')])
    add_fake_message(
        db.session, default_namespace.id, thread,
        from_addr=[('Bob', 'drive-shares-noreply@google.com')])

    noreply_contact = db.session.query(Contact).filter(
        Contact.namespace == default_namespace,
        Contact.email_address == 'drive-shares-noreply@google.com').one()
    assert noreply_contact.name is None

    add_fake_message(
        db.session, default_namespace.id, thread,
        from_addr=[('Alice', 'alice@example.com')])
    add_fake_message(
        db.session, default_namespace.id, thread,
        from_addr=[('Alice Lastname', 'alice@example.com')])

    contact = db.session.query(Contact).filter(
        Contact.namespace == default_namespace,
        Contact.email_address == 'alice@example.com').first()
    assert contact.name is not None
