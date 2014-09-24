"""Utility functions for creating, reading, updating and deleting contacts.
Called by the API."""
import uuid

from inbox.models import Contact

INBOX_PROVIDER_NAME = 'inbox'


def create(namespace, db_session, name, email):
    contact = Contact(
        namespace=namespace,
        source='local',
        provider_name=INBOX_PROVIDER_NAME,
        uid=uuid.uuid4().hex,
        name=name,
        email_address=email)
    db_session.add(contact)
    db_session.commit()
    return contact


def read(namespace, db_session, contact_public_id):
    return db_session.query(Contact).filter(
        Contact.public_id == contact_public_id,
        Contact.namespace_id == namespace.id).first()


def update(namespace, db_session, contact_public_id, name, email):
    raise NotImplementedError


def delete(namespace, db_session, contact_public_id):
    raise NotImplementedError
