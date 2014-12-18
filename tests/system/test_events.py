import pytest
import random
import datetime
import time

from inbox.client.errors import NotFoundError
from conftest import calendar_accounts, timeout_loop
from inbox.models.session import InboxSession
from inbox.ignition import main_engine

random.seed(None)


@pytest.yield_fixture(scope="module")
def real_db():
    """A fixture to get access to the real mysql db. We need this
    to log in to providers like gmail to check that events changes
    are synced back."""
    engine = main_engine()
    session = InboxSession(engine)
    yield session
    session.rollback()
    session.close()


@timeout_loop('calendar')
def wait_for_calendar(client, calendar_id):
    try:
        return client.calendars.find(calendar_id)
    except NotFoundError:
        return False


@timeout_loop('calendar')
def wait_for_calendar_deletion(client, calendar_id):
    try:
        client.calendars.find(calendar_id)
        return False
    except NotFoundError:
        return True


@pytest.mark.parametrize("client", calendar_accounts)
def test_calendar_creation(client):
    ns = client.namespaces[0]
    cal = ns.calendars.create()
    cal.name = "Random %d" % random.randint(1, 10000)
    cal.save()
    wait_for_calendar(client, cal.id)

    ns.calendars.delete(cal.id)
    wait_for_calendar_deletion(client, cal.id)


@timeout_loop('event')
def wait_for_event(client, event_id, real_db):
    try:
        return client.events.find(event_id)
    except NotFoundError:
        return False


@timeout_loop('event')
def wait_for_event_rename(client, event_id, new_title, real_db):
    try:
        ev = client.events.find(event_id)
        return ev.title == new_title
    except NotFoundError:
        return False


@timeout_loop('event')
def wait_for_event_deletion(client, event_id, real_db):
    try:
        client.events.find(event_id)
        return False
    except NotFoundError:
        return True


# We define this test function separately from test_event_crud
# because we want to be able to pass different types of accounts
# to it. For instance, test_event_crud here takes a list of
# generic accounts which support calendars but in test_google_events.py
# test_event_crud takes a list of gmail accounts.
# - karim
def real_test_event_crud(client, real_db):
    # create an event
    ns = client.namespaces[0]
    ev = ns.events.create()
    ev.calendar_id = ns.calendars[0].id
    ev.title = "Rodomontades"
    d1 = datetime.datetime.now() + datetime.timedelta(hours=2)
    d2 = datetime.datetime.now() + datetime.timedelta(hours=9)
    start = int(time.mktime(d1.timetuple()))
    end = int(time.mktime(d2.timetuple()))
    ev.when = {"start_time": start, "end_time": end}
    ev.save()
    wait_for_event(client, ev.id, real_db)

    # now, update it
    ev.title = "Renamed title"
    ev.participants = [{'email': 'bland@example.com', 'name': 'John Bland'}]
    ev.save()
    wait_for_event_rename(client, ev.id, ev.title, real_db)

    # finally, delete it
    ns.events.delete(ev.id)
    wait_for_event_deletion(client, ev.id, real_db)


@pytest.mark.parametrize("client", calendar_accounts)
def test_event_crud(client, real_db):
    real_test_event_crud(client, real_db)

if __name__ == '__main__':
    pytest.main([__file__])
