import uuid
from inbox.models import Contact, MessageContactAssociation


def update_contacts_from_message(db_session, message, account_id):
    with db_session.no_autoflush:
        for field in ('to_addr', 'from_addr', 'cc_addr', 'bcc_addr'):
            if getattr(message, field) is None:
                continue
            items = set(getattr(message, field))
            for name, email_address in items:
                contact = db_session.query(Contact).filter(
                    Contact.email_address == email_address).first()
                if contact is None:
                    contact = Contact(name=name, email_address=email_address,
                                      account_id=account_id, source='local',
                                      provider_name='inbox',
                                      uid=uuid.uuid4().hex)
                message.contacts.append(MessageContactAssociation(
                    contact=contact, field=field))
