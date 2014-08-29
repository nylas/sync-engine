"""Utility functions for creating, reading, updating and deleting events.
Called by the API."""
import uuid

from sqlalchemy.orm import subqueryload

from inbox.models import Account, Event
from inbox.events.ical import events_from_ics
from inbox.events.util import MalformedEventError

INBOX_PROVIDER_NAME = 'inbox'


def create(namespace, db_session, subject, body, location, reminders,
           recurrence, when, participants):
    account = db_session.query(Account).filter(
        Account.id == namespace.account_id).one()
    event = Event(
        calendar=account.default_calendar,
        account_id=namespace.account_id,
        uid=uuid.uuid4().hex,
        provider_name=INBOX_PROVIDER_NAME,
        raw_data='',
        subject=subject,
        body=body,
        location=location,
        when=when,
        read_only=False,
        is_owner=True,
        source='local')

    event.participant_list = participants

    db_session.add(event)
    db_session.commit()
    return event


def create_from_ics(namespace, db_session, ics_str):
    account = db_session.query(Account).filter(
        Account.id == namespace.account_id).one()
    try:
        events = events_from_ics(namespace, account.default_calendar, ics_str)
    except MalformedEventError:
        return None
    db_session.add_all(events)
    db_session.commit()
    return events


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
                 'when', 'participant_list']:
        if attr in update_dict:
            setattr(event, attr, update_dict[attr])

    db_session.add(event)
    db_session.commit()
    return event


def delete(namespace, db_session, event_public_id):
    raise NotImplementedError
