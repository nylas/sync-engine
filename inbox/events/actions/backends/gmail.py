""" Operations for syncing back local Calendar changes to Gmail. """

from inbox.events.google import GoogleEventsProvider

PROVIDER = 'gmail'

__all__ = ['remote_create_event', 'remote_update_event', 'remote_delete_event']


def remote_create_event(account, event, db_session):
    provider = GoogleEventsProvider(account.id, account.namespace.id)
    dump = provider.dump_event(event)
    service = provider._get_google_service()
    service.events().insert(calendarId='primary', body=dump).execute()


def remote_update_event(account, event, db_session):
    provider = GoogleEventsProvider(account.id, account.namespace.id)
    dump = provider.dump_event(event)
    service = provider._get_google_service()
    service.events().update(calendarId='primary',
                            eventId=event.uid, body=dump).execute()


def remote_delete_event(account, event, db_session):
    provider = GoogleEventsProvider(account.id, account.namespace.id)
    service = provider._get_google_service()
    service.events().delete(calendarId='primary', eventId=event.uid).execute()
