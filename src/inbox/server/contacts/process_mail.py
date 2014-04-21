import uuid

from inbox.server.models import session_scope
from inbox.server.models.tables.base import Contact


def update_contacts_from_message(account_id, message):
    with session_scope() as db_session:
        # TODO(emfree): Also calculate contact ranking scores.
        if message.from_addr is not None:
            name, email = message.from_addr
            maybe_add_contact(account_id, name, email, db_session)

        other_fields = (message.to_addr, message.cc_addr, message.bcc_addr)
        for field in other_fields:
            if field is None:
                continue
            for name, email in field:
                maybe_add_contact(account_id, name, email, db_session)

        db_session.commit()


def maybe_add_contact(account_id, name, email, db_session):
        existing_contacts = db_session.query(Contact).filter(
            Contact.email_address == email)
        if existing_contacts.count() == 0:
            db_session.add(Contact(name=name, email_address=email,
                                   account_id=account_id, source='local',
                                   provider_name='inbox', uid=uuid.uuid4()))
