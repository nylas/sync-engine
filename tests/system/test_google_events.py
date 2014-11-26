# Google calendar-specific event creation tests.
#
# This is a little hackish -- test_events.py defines a bunch of helper
# functions to check that an event appears on the API server. We redefine
# these functions to check instead for changes to the event on
# the Google backend.

import pytest
import random

from inbox.client.errors import NotFoundError
from inbox.events.google import GoogleEventsProvider
from inbox.models import Account

from conftest import gmail_accounts, timeout_loop
from test_events import real_db, real_test_event_crud

random.seed(None)


def get_api_access(db_session, email_address):
    account = db_session.query(Account).filter(
        Account.email_address == email_address).one()
    if account is None:
        raise Exception(("No account found for email address %s. "
                         "Are you sure you've authed it?") % email_address)

    return GoogleEventsProvider(account.id, account.namespace.id).\
        _get_google_service()


@timeout_loop('event')
def wait_for_event(client, event_id, real_db):
    try:
        ev = client.events.find(event_id)
        cal = client.calendars.find(ev.calendar_id)
        api = get_api_access(real_db, client.email_address)
        events = api.events().list(calendarId=cal.name).execute()
        for event in events['items']:
            if event['summary'] == ev.title:
                return True

        return False
    except NotFoundError:
        return False


@timeout_loop('event')
def wait_for_event_rename(client, event_id, new_title, real_db):
    try:
        ev = client.events.find(event_id)
        cal = client.calendars.find(ev.calendar_id)
        api = get_api_access(real_db, client.email_address)
        events = api.events().list(calendarId=cal.name).execute()
        for event in events['items']:
            if event['summary'] == new_title:
                return True

        return False
    except NotFoundError:
        return False


@timeout_loop('event')
def wait_for_event_deletion(client, calendar_id, event_title, real_db):
    try:
        cal = client.calendars.find(calendar_id)
        api = get_api_access(real_db, client.email_address)
        events = api.events().list(calendarId=cal.name).execute()
        for event in events['items']:
            if event['summary'] == event_title:
                return False

        return True
    except NotFoundError:
        return False


@pytest.mark.parametrize("client", gmail_accounts)
def test_event_crud(client, real_db):
    real_test_event_crud(client, real_db)


if __name__ == '__main__':
    pytest.main([__file__])
