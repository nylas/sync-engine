import pytest
import random
import datetime
import time

from inbox.client.errors import NotFoundError
from conftest import gmail_accounts, timeout_loop

random.seed(None)


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


@pytest.mark.parametrize("client", gmail_accounts)
def test_calendar_creation(client):
    ns = client.namespaces[0]
    cal = ns.calendars.create()
    cal.name = "Random %d" % random.randint(1, 10000)
    cal.save()
    wait_for_calendar(client, cal.id)

    ns.calendars.delete(cal.id)
    wait_for_calendar_deletion(client, cal.id)


@timeout_loop('event')
def wait_for_event(client, event_id):
    try:
        return client.events.find(event_id)
    except NotFoundError:
        return False


@timeout_loop('event')
def wait_for_event_rename(client, event_id, new_title):
    try:
        ev = client.events.find(event_id)
        return ev.title == new_title
    except NotFoundError:
        return False


@timeout_loop('event')
def wait_for_event_deletion(client, event_id):
    try:
        client.events.find(event_id)
        return False
    except NotFoundError:
        return True


@pytest.mark.parametrize("client", gmail_accounts)
def test_event_crud(client):
    # create an event
    ns = client.namespaces[0]
    ev = ns.events.create()
    ev.calendar_id = ns.calendars[0].id
    ev.title = "This is a test event"
    d1 = datetime.datetime.now() + datetime.timedelta(hours=2)
    d2 = datetime.datetime.now() + datetime.timedelta(hours=9)
    start = int(time.mktime(d1.timetuple()))
    end = int(time.mktime(d2.timetuple()))
    ev.when = {"start_time": start, "end_time": end}
    ev.save()
    wait_for_event(client, ev.id)

    # now, update it
    ev.title = "Renamed title"
    ev.save()
    wait_for_event_rename(client, ev.id, ev.title)

    # finally, delete it
    ns.events.delete(ev.id)
    wait_for_event_deletion(client, ev.id)


if __name__ == '__main__':
    pytest.main([__file__])
