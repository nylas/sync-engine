"""Utility functions for creating, reading, updating and deleting events.
Called by the API."""
import uuid

from sqlalchemy.orm import subqueryload

from inbox.models import Account, Event, Calendar
from inbox.events.ical import events_from_ics
from inbox.events.util import MalformedEventError
from inbox.api.validation import InputError

INBOX_PROVIDER_NAME = 'inbox'


def create(namespace, db_session, calendar, title, description, location,
           reminders, recurrence, when, participants):
    event = Event(
        calendar=calendar,
        account_id=namespace.account_id,
        uid=uuid.uuid4().hex,
        provider_name=INBOX_PROVIDER_NAME,
        raw_data='',
        title=title,
        description=description,
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
    eager = subqueryload(Event.participants_by_email)
    return db_session.query(Event).filter(
        Event.public_id == event_public_id,
        Event.account_id == namespace.account_id). \
        options(eager). \
        first()


def update(namespace, db_session, event_public_id, update_dict):
    eager = subqueryload(Event.participants_by_email)
    event = db_session.query(Event).filter(
        Event.public_id == event_public_id,
        Event.account_id == namespace.account_id). \
        options(eager). \
        first()

    if event is None:
        return event

    if event.read_only:
        raise InputError('Cannot update read_only event.')

    # Translate the calendar public_id to internal id
    if 'calendar_id' in update_dict:
        new_cal = db_session.query(Calendar).filter(
            Calendar.public_id == update_dict['calendar_id']).one()
        update_dict['calendar_id'] = new_cal.id

    for attr in ['title', 'description', 'location', 'reminders', 'recurrence',
                 'when', 'participant_list', 'calendar_id']:
        if attr in update_dict:
            setattr(event, attr, update_dict[attr])

    db_session.add(event)
    db_session.commit()
    return event


def delete(namespace, db_session, event_public_id):
    """ Delete the event with public_id = `event_public_id`. """
    event = db_session.query(Event).filter(
        Event.public_id == event_public_id).one()

    db_session.delete(event)
    db_session.commit()


##
# Calendar CRUD
##

def create_calendar(namespace, db_session, name, description):
    calendar = Calendar(
        account_id=namespace.account_id,
        name=name,
        provider_name=INBOX_PROVIDER_NAME,
        description=description,
        uid=uuid.uuid4().hex,
        read_only=False)

    db_session.add(calendar)
    db_session.commit()

    return calendar


def read_calendar(namespace, db_session, calendar_public_id):
    eager = subqueryload(Calendar.events). \
        subqueryload(Event.participants_by_email)
    return db_session.query(Calendar).filter(
        Calendar.public_id == calendar_public_id,
        Calendar.account_id == namespace.account_id). \
        options(eager). \
        first()


def update_calendar(namespace, db_session, calendar_public_id, update_dict):
    eager = subqueryload(Calendar.events). \
        subqueryload(Event.participants_by_email)
    calendar = db_session.query(Calendar).filter(
        Calendar.public_id == calendar_public_id,
        Calendar.account_id == namespace.account_id). \
        options(eager). \
        first()

    if calendar is None:
        return calendar

    for attr in ['name', 'description']:
        if attr in update_dict:
            setattr(calendar, attr, update_dict[attr])

    db_session.commit()
    return calendar


def delete_calendar(namespace, db_session, calendar_public_id):
    """ Delete the calendar with public_id = `calendar_public_id`. """
    calendar = db_session.query(Calendar).filter(
        Calendar.public_id == calendar_public_id).first()

    db_session.delete(calendar)
    db_session.commit()
