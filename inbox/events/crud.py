"""Utility functions for creating, reading, updating and deleting events.
Called by the API."""
import uuid

from inbox.models import Event

INBOX_PROVIDER_NAME = 'inbox'


def create(namespace, db_session, subject, body, location, reminders,
           recurrence, start, end, busy, all_day):
    event = Event(
        account_id=namespace.account_id,
        uid=uuid.uuid4().hex,
        provider_name=INBOX_PROVIDER_NAME,
        raw_data='',
        subject=subject,
        body=body,
        location=location,
        reminders=reminders,
        recurrence=recurrence,
        start=start,
        end=end,
        busy=busy,
        all_day=all_day,
        locked=False,
        time_zone=0,
        source='local')
    db_session.add(event)
    db_session.commit()
    return event


def read(namespace, db_session, event_public_id):
    return db_session.query(Event).filter(
        Event.public_id == event_public_id,
        Event.account_id == namespace.account_id).first()


def update(namespace, db_session, event_public_id, name, email):
    raise NotImplementedError


def delete(namespace, db_session, event_public_id):
    raise NotImplementedError
