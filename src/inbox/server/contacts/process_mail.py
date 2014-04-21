"""Support for adding and ranking contacts based on mail data."""
import calendar
import uuid

from inbox.server.contacts import search_util
from inbox.server.models import session_scope
from inbox.server.models.tables.base import Contact


def canonicalize_address(address):
    """Gmail addresses with and without periods are the same, so we want to
    treat them as belonging to the same contact."""
    # "foo@bar"@example.com is technically a valid email address, so you
    # can't just do address.split('@').
    at_index = address.rfind('@')
    domain = address[at_index + 1:]
    local_part = address[:at_index]
    if domain in ('gmail.com', 'googlemail.com'):
        local_part = local_part.translate(None, '.')
    return '@'.join((local_part, domain))


def update_contacts_from_message(account_id, message):
    """Add new contacts from the given message's to/from/cc fields, and update
    ranking scores for all contacts in those fields."""
    with session_scope() as db_session:
        from_contacts = get_contact_objects(
            account_id, [message.from_addr], db_session)
        to_contacts = get_contact_objects(
            account_id, message.to_addr, db_session)
        cc_contacts = get_contact_objects(
            account_id, message.cc_addr, db_session)
        bcc_contacts = get_contact_objects(
            account_id, message.bcc_addr, db_session)

        msg_timestamp = calendar.timegm(message.received_date.utctimetuple())

        for contact in to_contacts:
            search_util.increment_signal(contact, 'to_count')
            search_util.update_timestamp_signal(contact, msg_timestamp)

        for contact in cc_contacts:
            search_util.increment_signal(contact, 'cc_count')
            search_util.update_timestamp_signal(contact, msg_timestamp)

        for contact in bcc_contacts:
            search_util.increment_signal(contact, 'bcc_count')
            search_util.update_timestamp_signal(contact, msg_timestamp)

        for contact in from_contacts:
            search_util.increment_signal(contact, 'from_count')
            search_util.update_timestamp_signal(contact, msg_timestamp)

        for contact in to_contacts + cc_contacts + from_contacts:
            # TODO(emfree): We may be recomputing the score many more times
            # than needed. If this has performance implications, hoist the
            # score computation.
            search_util.score(contact)

        db_session.commit()


def get_contact_objects(account_id, addresses, db_session):
    """Given a list `addresses` of (name, email) pairs, return existing
    contacts with matching email. Create and also return contact objects for
    any email without a match."""
    contacts = []
    for address in addresses:
        if address is None:
            continue
        name, email = address
        canonical_email = canonicalize_address(email)
        existing_contacts = db_session.query(Contact). \
            filter(Contact.email_address == canonical_email,
                   Contact.account_id == account_id).all()
        if not existing_contacts:
            new_contact = Contact(name=name, email_address=canonical_email,
                                  account_id=account_id, source='local',
                                  provider_name='inbox', uid=uuid.uuid4())
            contacts.append(new_contact)
            db_session.add(new_contact)
        else:
            contacts.extend(existing_contacts)
    return contacts
