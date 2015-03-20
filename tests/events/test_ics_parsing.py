# -*- coding: utf-8 -*-

import pytest
import arrow
from inbox.models.event import Event, RecurringEvent
from inbox.events.util import MalformedEventError
from inbox.events.ical import events_from_ics, import_attached_events
from tests.util.base import absolute_path

FIXTURES = './events/fixtures/'


def test_invalid_ical(db, default_account):
    with pytest.raises(MalformedEventError):
        events_from_ics(default_account.namespace,
                        default_account.emailed_events_calendar, "asdf")


def test_windows_tz_ical(db, default_account):
    data = None
    with open(absolute_path(FIXTURES + 'windows_event.ics')) as fd:
        data = fd.read()

    events = events_from_ics(default_account.namespace,
                             default_account.emailed_events_calendar, data)
    assert len(events) == 1, "There should be only one event in the test file"

    ev = events[0]
    assert ev.start == arrow.get(2015, 2, 20, 8, 30)
    assert ev.end == arrow.get(2015, 2, 20, 9, 0)
    assert ev.title == "Pommes"
    assert len(ev.participants) == 1
    assert ev.participants[0]['email'] == 'karim@nilas.com'


def test_icloud_allday_event(db, default_account):
    data = None
    with open(absolute_path(FIXTURES + 'icloud_oneday_event.ics')) as fd:
        data = fd.read()

    events = events_from_ics(default_account.namespace,
                             default_account.emailed_events_calendar, data)
    assert len(events) == 1, "There should be only one event in the test file"

    ev = events[0]
    assert ev.all_day is True
    assert ev.start == arrow.get(2015, 3, 16, 0, 0)
    assert ev.end == arrow.get(2015, 3, 17, 0, 0)

    assert len(ev.participants) == 2
    assert ev.participants[0]['email'] == 'karim@nilas.com'


def test_iphone_through_exchange(db, default_account):
    data = None
    with open(absolute_path(FIXTURES + 'iphone_through_exchange.ics')) as fd:
        data = fd.read()

    events = events_from_ics(default_account.namespace,
                             default_account.emailed_events_calendar, data)
    assert len(events) == 1, "There should be only one event in the test file"

    ev = events[0]
    assert ev.start == arrow.get(2014, 12, 27, 15, 0)
    assert ev.end == arrow.get(2014, 12, 27, 16, 0)


def test_event_update(db, default_account):

    with open(absolute_path(FIXTURES + 'gcal_v1.ics')) as fd:
        data = fd.read()

    import_attached_events(default_account.id, data)
    db.session.commit()

    ev = db.session.query(Event).filter(
        Event.uid == "jvbroggos139aumnj4p5og9rd0@google.com").one()

    assert ev.location == ("Olympia Hall, 28 Boulevard des Capucines, "
                           "75009 Paris, France")

    with open(absolute_path(FIXTURES + 'gcal_v2.ics')) as fd:
        data = fd.read()

    import_attached_events(default_account.id, data)
    db.session.commit()

    ev = db.session.query(Event).filter(
        Event.uid == "jvbroggos139aumnj4p5og9rd0@google.com").one()

    assert ev.location == (u"Le Zenith, 211 Avenue Jean Jaures, "
                           "75019 Paris, France")


def test_recurring_ical(db, default_account):

    with open(absolute_path(FIXTURES + 'gcal_recur.ics')) as fd:
        data = fd.read()

    import_attached_events(default_account.id, data)
    db.session.commit()

    ev = db.session.query(Event).filter(
        Event.uid == "flg2h6nam1cb1uqetgfkslrfrc@google.com").one()

    assert isinstance(ev, RecurringEvent)
    assert isinstance(ev.recurring, list)
    assert ev.start_timezone == 'America/Los_Angeles'


def test_event_no_end_time(db, default_account):
    # With no end time, import should fail
    with open(absolute_path(FIXTURES + 'meetup_infinite.ics')) as fd:
        data = fd.read()

    with pytest.raises(MalformedEventError) as exc:
        import_attached_events(default_account.id, data)

        assert exc.message == 'Event lacks start and/or end time'


def test_event_no_participants(db, default_account):
    data = None
    with open(absolute_path(FIXTURES + 'event_with_no_participants.ics')) as fd:
        data = fd.read()

    events = events_from_ics(default_account.namespace,
                             default_account.emailed_events_calendar, data)
    assert len(events) == 1, "There should be only one event in the test file"
    ev = events[0]
    assert len(ev.participants) == 0


def test_multiple_events(db, default_account):
    data = None
    with open(absolute_path(FIXTURES + 'multiple_events.ics')) as fd:
        data = fd.read()

    events = events_from_ics(default_account.namespace,
                             default_account.emailed_events_calendar, data)
    assert len(events) == 2
    ev0 = events[0]
    ev1 = events[1]
    assert len(ev0.participants) == 0
    assert len(ev1.participants) == 0

    assert ev1.start == arrow.get(2015, 03, 17, 0, 0)
