import pytest
import datetime
from inbox.events.google import MalformedEventError
from inbox.events.ical import events_from_ics


def test_invalid_ical(db, default_account):
    with pytest.raises(MalformedEventError):
        events_from_ics(default_account.namespace,
                        default_account.default_calendar, "asdf")


def test_windows_tz_ical(db, default_account):
    data = None
    with open('./fixtures/windows_event.ics') as fd:
        data = fd.read()

    events = events_from_ics(default_account.namespace, default_account.default_calendar, data)
    assert len(events) == 1, "There should be only one event in the test file"

    ev = events[0]
    assert ev.start == datetime.datetime(2015, 2, 20, 8, 30)
    assert ev.end == datetime.datetime(2015, 2, 20, 9, 0)
    assert ev.title ==  "Pommes"
    assert len(ev.participants) == 1
    assert ev.participants[0]['email'] == 'karim@nilas.com'


def test_icloud_allday_event(db, default_account):
    data = None
    with open('./fixtures/icloud_oneday_event.ics') as fd:
        data = fd.read()

    events = events_from_ics(default_account.namespace, default_account.default_calendar, data)
    assert len(events) == 1, "There should be only one event in the test file"

    ev = events[0]
    assert ev.all_day is True
    assert ev.start == datetime.datetime(2015, 3, 16, 0, 0)
    assert ev.end == datetime.datetime(2015, 3, 17, 0, 0)

    assert len(ev.participants) == 2
    assert ev.participants[0]['email'] == 'karim@nilas.com'
