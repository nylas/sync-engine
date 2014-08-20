"""Utility functions for creating, reading, updating and deleting events.
Called by the API."""
import uuid

from inbox.models import Event
from sqlalchemy.orm import subqueryload

INBOX_PROVIDER_NAME = 'inbox'


def create(namespace, db_session, subject, body, location, reminders,
           recurrence, start, end, busy, all_day, participants):
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

    event.participant_list = participants

    db_session.add(event)
    db_session.commit()
    return event


def read(namespace, db_session, event_public_id):
    return db_session.query(Event).filter(
        Event.public_id == event_public_id,
        Event.account_id == namespace.account_id). \
        options(subqueryload(Event.participants_by_email)). \
        first()


def update(namespace, db_session, event_public_id, update_dict):
    event = db_session.query(Event).filter(
        Event.public_id == event_public_id,
        Event.account_id == namespace.account_id). \
        options(subqueryload(Event.participants_by_email)). \
        first()

    if event is None:
        return event

    for attr in ['subject', 'body', 'location', 'reminders', 'recurrence',
                 'start', 'end', 'busy', 'all_day', 'participant_list']:
        if attr in update_dict:
            setattr(event, attr, update_dict[attr])

    db_session.add(event)
    db_session.commit()
    return event


def delete(namespace, db_session, event_public_id):
    raise NotImplementedError
