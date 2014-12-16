""" Operations for syncing back local Calendar changes to Gmail. """

from inbox.events.google import GoogleEventsProvider

PROVIDER = 'gmail'

__all__ = ['remote_create_event', 'remote_update_event', 'remote_delete_event']


def remote_create_event(account, event, db_session):
    provider = GoogleEventsProvider(account.id, account.namespace.id)
    dump = provider.dump_event(event)
    service = provider._get_google_service()
    result = service.events().insert(calendarId=event.calendar.name,
                                     body=dump).execute()
    # The events crud API assigns a random uid to an event when creating it.
    # We need to update it to the value returned by the Google calendar API.
    event.uid = result['id']
    db_session.commit()


def remote_update_event(account, event, db_session):
    provider = GoogleEventsProvider(account.id, account.namespace.id)
    dump = provider.dump_event(event)
    service = provider._get_google_service()
    service.events().update(calendarId=event.calendar.name,
                            eventId=event.uid, body=dump).execute()


def remote_delete_event(account, event_uid, calendar_name, db_session):
    provider = GoogleEventsProvider(account.id, account.namespace.id)
    service = provider._get_google_service()
    service.events().delete(calendarId=calendar_name,
                            eventId=event_uid).execute()
