from datetime import datetime
from inbox.events.remote_sync import EventSync
from inbox.models import Calendar, Event, Transaction
from tests.util.base import new_account


# Placeholder values for non-nullable attributes
default_params = dict(raw_data='',
                      busy=True,
                      all_day=False,
                      read_only=False,
                      start=datetime(2015, 2, 22, 11, 11),
                      end=datetime(2015, 2, 22, 22, 22),
                      is_owner=True,
                      participants=[])


# Mock responses from the provider with adds/updates/deletes


def calendar_response():
    return ([], [
        Calendar(name='Important Meetings',
                 uid='first_calendar_uid',
                 read_only=False),
        Calendar(name='Nefarious Schemes',
                 uid='second_calendar_uid',
                 read_only=False),
    ])


def calendar_response_with_update():
    return ([], [Calendar(name='Super Important Meetings',
                          uid='first_calendar_uid',
                          read_only=False)])


def calendar_response_with_delete():
    return (['first_calendar_uid'], [])


def event_response(calendar_uid, sync_from_time):
    if calendar_uid == 'first_calendar_uid':
        return ([], [
            Event(uid='first_event_uid',
                  title='Plotting Meeting',
                  **default_params),
            Event(uid='second_event_uid',
                  title='Scheming meeting',
                  **default_params),
            Event(uid='third_event_uid',
                  title='Innocent Meeting',
                  **default_params)
        ])
    else:
        return ([], [
            Event(uid='second_event_uid',
                  title='Plotting Meeting',
                  **default_params),
            Event(uid='third_event_uid',
                  title='Scheming meeting',
                  **default_params)
        ])


def event_response_with_update(calendar_uid, sync_from_time):
    if calendar_uid == 'first_calendar_uid':
        return ([], [Event(uid='first_event_uid',
                           title='Top Secret Plotting Meeting',
                           **default_params)])


def event_response_with_delete(calendar_uid, sync_from_time):
    if calendar_uid == 'first_calendar_uid':
        return (['first_event_uid'], [])


def test_handle_changes(db, new_account):
    namespace_id = new_account.namespace.id
    event_sync = EventSync(new_account.email_address, 'google', new_account.id,
                           namespace_id)

    # Sync calendars/events
    event_sync.provider.sync_calendars = calendar_response
    event_sync.provider.sync_events = event_response
    event_sync.sync()

    assert db.session.query(Calendar).filter(
        Calendar.namespace_id == namespace_id).count() == 2

    assert db.session.query(Event).join(Calendar).filter(
        Event.namespace_id == namespace_id,
        Calendar.uid == 'first_calendar_uid').count() == 3

    assert db.session.query(Event).join(Calendar).filter(
        Event.namespace_id == namespace_id,
        Calendar.uid == 'second_calendar_uid').count() == 2

    # Sync a calendar update
    event_sync.provider.sync_calendars = calendar_response_with_update
    event_sync.provider.sync_events = event_response
    event_sync.sync()

    # Check that we have the same number of calendars and events as before
    assert db.session.query(Calendar).filter(
        Calendar.namespace_id == namespace_id).count() == 2

    assert db.session.query(Event).join(Calendar).filter(
        Event.namespace_id == namespace_id,
        Calendar.uid == 'first_calendar_uid').count() == 3

    assert db.session.query(Event).join(Calendar).filter(
        Event.namespace_id == namespace_id,
        Calendar.uid == 'second_calendar_uid').count() == 2

    # Check that calendar attribute was updated.
    first_calendar = db.session.query(Calendar).filter(
        Calendar.namespace_id == namespace_id,
        Calendar.uid == 'first_calendar_uid').one()
    assert first_calendar.name == 'Super Important Meetings'

    # Sync an event update
    event_sync.provider.sync_events = event_response_with_update
    event_sync.sync()
    # Make sure the update was persisted
    first_event = db.session.query(Event).filter(
        Event.namespace_id == namespace_id,
        Event.calendar_id == first_calendar.id,
        Event.uid == 'first_event_uid').one()
    assert first_event.title == 'Top Secret Plotting Meeting'

    # Sync an event delete
    event_sync.provider.sync_events = event_response_with_delete
    event_sync.sync()
    # Make sure the delete was persisted.
    first_event = db.session.query(Event).filter(
        Event.namespace_id == namespace_id,
        Event.calendar_id == first_calendar.id,
        Event.uid == 'first_event_uid').first()
    assert first_event is None

    # Sync a calendar delete
    event_public_ids = [id_ for id_, in db.session.query(Event.public_id).
                        filter(Event.namespace_id == namespace_id,
                               Event.calendar_id == first_calendar.id)]
    event_sync.provider.sync_calendars = calendar_response_with_delete
    event_sync.sync()
    assert db.session.query(Calendar).filter(
        Calendar.namespace_id == namespace_id,
        Calendar.uid == 'first_calendar_uid').first() is None

    # Check that delete transactions are created for events on the deleted
    # calendar.
    deleted_event_transactions = db.session.query(Transaction).filter(
        Transaction.object_type == 'event',
        Transaction.command == 'delete',
        Transaction.namespace_id == namespace_id,
        Transaction.object_public_id.in_(event_public_ids)).all()
    assert len(deleted_event_transactions) == 2

    # Check that events with the same uid but associated to a different
    # calendar still survive.
    assert db.session.query(Event).filter(
        Event.namespace_id == namespace_id).count() == 2
