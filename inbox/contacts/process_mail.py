"""Support for adding and ranking contacts based on mail data."""
import calendar
import uuid

from inbox.contacts import search_util
from inbox.models import Contact, MessageContactAssociation
from inbox.util.addr import canonicalize_address

SIGNAL_NAME_MAPPING = {
    'to_addr': 'to_count',
    'from_addr': 'from_count',
    'cc_addr': 'cc_count',
    'bcc_addr': 'bcc_count',
}


def update_contacts(db_session, account_id, message):
    """Add new contacts from the given message's to/from/cc fields, and update
    ranking scores for all contacts in those fields."""
    msg_timestamp = calendar.timegm(message.received_date.utctimetuple())

    for field in ['to_addr', 'cc_addr', 'bcc_addr', 'from_addr']:
        addresses = getattr(message, field)

        contacts = get_contact_objects(db_session, account_id, addresses)

        for contact in contacts:
            search_util.increment_signal(contact, SIGNAL_NAME_MAPPING[field])
            search_util.update_timestamp_signal(contact, msg_timestamp)
            update_association(db_session, message, contact, field)
            search_util.score(contact)


def update_association(db_session, message, contact, field):
    with db_session.no_autoflush:
        # We need to temporarily disable autoflush to prevent the sqlalchemy
        # error `OperationalError: (OperationalError) (1364, "Field
        # 'message_id' doesn't have a default value")`.
        association = MessageContactAssociation(field=field)
        association.contact = contact
        message.contacts.append(association)


def get_contact_objects(db_session, account_id, addresses):
    """Given a list `addresses` of (name, email) pairs, return existing
    contacts with matching email. Create and also return contact objects for
    any email without a match."""
    if addresses is None:
        return []
    contacts = []
    for addr in addresses:
        if addr is None:
            continue
        name, email = addr
        canonical_email = canonicalize_address(email)
        existing_contacts = db_session.query(Contact). \
            filter(Contact.email_address == canonical_email,
                   Contact.account_id == account_id).all()
        if not existing_contacts:
            new_contact = Contact(name=name,
                                  email_address=canonical_email,
                                  account_id=account_id, source='local',
                                  provider_name='inbox', uid=uuid.uuid4().hex)
            contacts.append(new_contact)
            db_session.add(new_contact)
        else:
            contacts.extend(existing_contacts)
    return contacts
