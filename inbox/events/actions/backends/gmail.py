""" Operations for syncing back local Calendar changes to Gmail. """

from inbox.events.google import GoogleEventsProvider

PROVIDER = 'gmail'

__all__ = ['remote_create', 'remote_update', 'remote_delete']


def remote_create(account, event, db_session):
    provider = GoogleEventsProvider(account.id, account.namespace.id)
    dump = provider.dump_event(event)
    service = provider._get_google_service()
    service.events().insert(calendarId='primary', body=dump).execute()


def remote_update(account, event, db_session):
    provider = GoogleEventsProvider(account.id, account.namespace.id)
    dump = provider.dump_event(event)
    service = provider._get_google_service()
    service.events().update(calendarId='primary',
                            eventId=event.uid, body=dump).execute()


def remote_delete(account, event, db_session):
    provider = GoogleEventsProvider(account.id, account.namespace.id)
    service = provider._get_google_service()
    service.events().delete(calendarId='primary', eventId=event.uid).execute()
