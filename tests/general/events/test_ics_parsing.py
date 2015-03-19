# -*- coding: utf-8 -*-

import pytest
import datetime
from inbox.models.event import Event
from inbox.events.util import MalformedEventError
from inbox.events.ical import events_from_ics, import_attached_events
from tests.util.base import absolute_path, add_fake_calendar


def test_invalid_ical(db, default_account):
    with pytest.raises(MalformedEventError):
        events_from_ics(default_account.namespace,
                        default_account.emailed_events_calendar, "asdf")


def test_windows_tz_ical(db, default_account):
    data = None
    with open(absolute_path('./general/events/fixtures/windows_event.ics')) as fd:
        data = fd.read()

    events = events_from_ics(default_account.namespace,
                             default_account.emailed_events_calendar, data)
    assert len(events) == 1, "There should be only one event in the test file"

    ev = events[0]
    assert ev.start == datetime.datetime(2015, 2, 20, 8, 30)
    assert ev.end == datetime.datetime(2015, 2, 20, 9, 0)
    assert ev.title == "Pommes"
    assert len(ev.participants) == 1
    assert ev.participants[0]['email'] == 'karim@nilas.com'


def test_icloud_allday_event(db, default_account):
    data = None
    with open(absolute_path('./general/events/fixtures/icloud_oneday_event.ics')) as fd:
        data = fd.read()

    events = events_from_ics(default_account.namespace,
                             default_account.emailed_events_calendar, data)
    assert len(events) == 1, "There should be only one event in the test file"

    ev = events[0]
    assert ev.all_day is True
    assert ev.start == datetime.datetime(2015, 3, 16, 0, 0)
    assert ev.end == datetime.datetime(2015, 3, 17, 0, 0)

    assert len(ev.participants) == 2
    assert ev.participants[0]['email'] == 'karim@nilas.com'


def test_iphone_through_exchange(db, default_account):
    data = None
    with open(absolute_path('./general/events/fixtures/iphone_through_exchange.ics')) as fd:
        data = fd.read()

    events = events_from_ics(default_account.namespace,
                             default_account.emailed_events_calendar, data)
    assert len(events) == 1, "There should be only one event in the test file"

    ev = events[0]
    assert ev.start == datetime.datetime(2014, 12, 27, 15, 0)
    assert ev.end == datetime.datetime(2014, 12, 27, 16, 0)


def test_event_update(db, default_account):
    cal = add_fake_calendar(db.session, default_account.namespace.id,
                            name="Emailed events", read_only=True)

    data = None
    with open(absolute_path('./general/events/fixtures/gcal_v1.ics')) as fd:
        data = fd.read()

    import_attached_events(default_account.id, data)
    db.session.commit()

    ev = db.session.query(Event).filter(
        Event.uid == "jvbroggos139aumnj4p5og9rd0@google.com").one()

    assert ev.location == ("Olympia Hall, 28 Boulevard des Capucines, "
                           "75009 Paris, France")

    with open(absolute_path('./general/events/fixtures/gcal_v2.ics')) as fd:
        data = fd.read()

    import_attached_events(default_account.id, data)
    db.session.commit()

    ev = db.session.query(Event).filter(
        Event.uid == "jvbroggos139aumnj4p5og9rd0@google.com").one()

    assert ev.location == (u"Le Zenith, 211 Avenue Jean Jaures, "
                            "75019 Paris, France")
