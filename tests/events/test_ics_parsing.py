# -*- coding: utf-8 -*-

import pytest
import arrow
from datetime import datetime
from flanker import mime
from inbox.models import Message
from inbox.models.event import Event, RecurringEvent
from inbox.events.util import MalformedEventError
from inbox.events.ical import events_from_ics, import_attached_events
from tests.util.base import (absolute_path, add_fake_calendar,
                             add_fake_thread, generic_account,
                             add_fake_msg_with_calendar_part)

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
    events = events['invites']
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
    events = events['invites']
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
    events = events['invites']
    assert len(events) == 1, "There should be only one event in the test file"

    ev = events[0]
    assert ev.start == arrow.get(2014, 12, 27, 15, 0)
    assert ev.end == arrow.get(2014, 12, 27, 16, 0)


@pytest.mark.parametrize('from_value', [[], [["", ""]], [[""]]])
def test_invalid_sender(from_value, db, default_account):
    # Check that messages with an invalid from field get discarded.
    data = None
    event_count = db.session.query(Event).count()

    with open(absolute_path(FIXTURES + 'iphone_through_exchange.ics')) as fd:
        data = fd.read()

    msg = add_fake_msg_with_calendar_part(db.session, default_account,
                                          data)
    msg.from_addr = from_value
    db.session.add(msg)
    db.session.commit()

    import_attached_events(db.session, default_account, msg)
    db.session.commit()

    event_count2 = db.session.query(Event).count()
    assert event_count == event_count2, "The event shouldn't have been added"


def test_event_update(db, default_account, message):
    add_fake_calendar(db.session, default_account.namespace.id,
                      name="Emailed events", read_only=True)

    with open(absolute_path(FIXTURES + 'gcal_v1.ics')) as fd:
        ics_data = fd.read()

    msg = add_fake_msg_with_calendar_part(db.session, default_account,
                                          ics_data)

    import_attached_events(db.session, default_account, msg)
    db.session.commit()

    ev = db.session.query(Event).filter(
        Event.uid == "jvbroggos139aumnj4p5og9rd0@google.com").one()

    assert ev.location == ("Olympia Hall, 28 Boulevard des Capucines, "
                           "75009 Paris, France")

    with open(absolute_path(FIXTURES + 'gcal_v2.ics')) as fd:
        ics_data = fd.read()

    msg = add_fake_msg_with_calendar_part(
        db.session, default_account, ics_data)

    import_attached_events(db.session, default_account, msg)
    db.session.commit()

    ev = db.session.query(Event).filter(
        Event.uid == "jvbroggos139aumnj4p5og9rd0@google.com").one()

    assert ev.location == (u"Le Zenith, 211 Avenue Jean Jaures, "
                            "75019 Paris, France")


def test_recurring_ical(db, default_account):
    with open(absolute_path(FIXTURES + 'gcal_recur.ics')) as fd:
        ics_data = fd.read()

    msg = add_fake_msg_with_calendar_part(
        db.session, default_account, ics_data)

    import_attached_events(db.session, default_account, msg)
    db.session.commit()

    ev = db.session.query(Event).filter(
        Event.uid == "flg2h6nam1cb1uqetgfkslrfrc@google.com").one()

    assert isinstance(ev, RecurringEvent)
    assert isinstance(ev.recurring, list)
    assert ev.start_timezone == 'America/Los_Angeles'


def test_event_no_end_time(db, default_account):
    # With no end time, import should fail
    with open(absolute_path(FIXTURES + 'meetup_infinite.ics')) as fd:
        ics_data = fd.read()

    add_fake_msg_with_calendar_part(db.session, default_account, ics_data)

    # doesn't raise an exception (to not derail message parsing, but also
    # doesn't create an event)
    ev = db.session.query(Event).filter(
        Event.uid == "nih2h78am1cb1uqetgfkslrfrc@meetup.com").first()
    assert not ev


def test_event_no_participants(db, default_account):
    data = None
    with open(absolute_path(FIXTURES + 'event_with_no_participants.ics')) as fd:
        data = fd.read()

    events = events_from_ics(default_account.namespace,
                             default_account.emailed_events_calendar, data)
    events = events['invites']
    assert len(events) == 1, "There should be only one event in the test file"
    ev = events[0]
    assert len(ev.participants) == 0


def test_multiple_events(db, default_account):
    data = None
    with open(absolute_path(FIXTURES + 'multiple_events.ics')) as fd:
        data = fd.read()

    events = events_from_ics(default_account.namespace,
                             default_account.emailed_events_calendar, data)
    events = events['invites']
    assert len(events) == 2
    ev0 = events[0]
    ev1 = events[1]
    assert len(ev0.participants) == 0
    assert len(ev1.participants) == 0

    assert ev1.start == arrow.get(2015, 03, 17, 0, 0)


def test_icalendar_import(db, generic_account, message):
    add_fake_calendar(db.session, generic_account.namespace.id,
                      name="Emailed events", read_only=True)

    with open(absolute_path(FIXTURES + 'invite_w_rsvps1.ics')) as fd:
        ics_data = fd.read()

    msg = add_fake_msg_with_calendar_part(
        db.session, generic_account, ics_data)

    import_attached_events(db.session, generic_account, msg)

    ev = db.session.query(Event).filter(
        Event.uid == ("040000008200E00074C5B7101A82E00800000000"
                      "F9125A30B06BD001000000000000000010000000"
                      "9D791C7548BFD144BFA54F14213CAD25")).one()

    assert len(ev.participants) == 2
    for participant in ev.participants:
        assert participant['status'] == 'noreply'


def test_rsvp_merging(db, generic_account, message):
    # This test checks that RSVPs to invites we sent get merged.
    # It does some funky stuff around calendars because by default
    # autoimported invites end up in the "emailed events" calendar.
    # However, we're simulating invite sending, which supposes using
    # an event from another calendar.
    add_fake_calendar(db.session, generic_account.namespace.id,
                      name="Emailed events", read_only=True)
    cal2 = add_fake_calendar(db.session, generic_account.namespace.id,
                             name="Random calendar", read_only=True)

    with open(absolute_path(FIXTURES + 'invite_w_rsvps1.ics')) as fd:
        ics_data = fd.read()

    msg = add_fake_msg_with_calendar_part(
        db.session, generic_account, ics_data)

    import_attached_events(db.session, generic_account, msg)

    ev = db.session.query(Event).filter(
        Event.uid == ("040000008200E00074C5B7101A82E00800000000"
                      "F9125A30B06BD001000000000000000010000000"
                      "9D791C7548BFD144BFA54F14213CAD25")).one()

    assert len(ev.participants) == 2
    for participant in ev.participants:
        assert participant['status'] == 'noreply'

    ev.public_id = "cccc"
    ev.calendar = cal2

    with open(absolute_path(FIXTURES + 'invite_w_rsvps2.ics')) as fd:
        ics_data = fd.read()

    msg2 = add_fake_msg_with_calendar_part(
        db.session, generic_account, ics_data)

    import_attached_events(db.session, generic_account, msg2)

    ev = db.session.query(Event).filter(
        Event.uid == ("040000008200E00074C5B7101A82E00800000000"
                      "F9125A30B06BD001000000000000000010000000"
                      "9D791C7548BFD144BFA54F14213CAD25")).one()

    assert len(ev.participants) == 2
    for participant in ev.participants:
        if participant['email'] == 'test1@example.com':
            assert participant['status'] == 'maybe'
            assert participant['name'] == 'Inbox Apptest'
        elif participant['email'] == 'karim@example.com':
            assert participant['status'] == 'noreply'

    with open(absolute_path(FIXTURES + 'invite_w_rsvps3.ics')) as fd:
        ics_data = fd.read()

    msg3 = add_fake_msg_with_calendar_part(
        db.session, generic_account, ics_data)

    import_attached_events(db.session, generic_account, msg3)

    ev = db.session.query(Event).filter(
        Event.uid == ("040000008200E00074C5B7101A82E00800000000"
                      "F9125A30B06BD001000000000000000010000000"
                      "9D791C7548BFD144BFA54F14213CAD25")).one()

    assert len(ev.participants) == 2

    for participant in ev.participants:
        if participant['email'] == 'test1@example.com':
            assert participant['status'] == 'maybe'
            assert participant['name'] == 'Inbox Apptest'
        elif participant['email'] == 'karim@example.com':
            assert participant['name'] == 'Karim Hamidou'
            assert participant['status'] == 'yes'

    # Check that we're handling sequence numbers correctly - i.e: an RSVP
    # with a sequence number < to the event's sequence number should be
    # discarded.
    ev.sequence_number += 1

    with open(absolute_path(FIXTURES + 'invite_w_rsvps_4.ics')) as fd:
        ics_data = fd.read()

    msg4 = add_fake_msg_with_calendar_part(
        db.session, generic_account, ics_data)

    import_attached_events(db.session, generic_account, msg3)

    ev = db.session.query(Event).filter(
        Event.uid == ("040000008200E00074C5B7101A82E00800000000"
                      "F9125A30B06BD001000000000000000010000000"
                      "9D791C7548BFD144BFA54F14213CAD25")).one()

    assert len(ev.participants) == 2
    for participant in ev.participants:
        if participant['email'] == 'test1@example.com':
            assert participant['status'] == 'maybe'
            assert participant['name'] == 'Inbox Apptest'
        elif participant['email'] == 'karim@example.com':
            assert participant['name'] == 'Karim Hamidou'
            assert participant['status'] == 'yes'


def test_cancelled_event(db, default_account):
    with open(absolute_path(FIXTURES + 'google_cancelled1.ics')) as fd:
        ics_data = fd.read()

    msg = add_fake_msg_with_calendar_part(
        db.session, default_account, ics_data)

    import_attached_events(db.session, default_account, msg)
    db.session.commit()

    ev = db.session.query(Event).filter(
        Event.uid == "c74p2nmutcd0kt69ku7rs8vu2g@google.com").one()

    assert ev.status == 'confirmed'

    with open(absolute_path(FIXTURES + 'google_cancelled2.ics')) as fd:
        ics_data = fd.read()

    msg2 = add_fake_msg_with_calendar_part(
        db.session, default_account, ics_data)

    import_attached_events(db.session, default_account, msg2)
    db.session.commit()

    ev = db.session.query(Event).filter(
        Event.uid == "c74p2nmutcd0kt69ku7rs8vu2g@google.com").one()

    assert ev.status == 'cancelled'


def test_icloud_cancelled_event(db, default_account):
    with open(absolute_path(FIXTURES + 'icloud_cancelled1.ics')) as fd:
        ics_data = fd.read()

    msg = add_fake_msg_with_calendar_part(
        db.session, default_account, ics_data)

    import_attached_events(db.session, default_account, msg)
    db.session.commit()

    ev = db.session.query(Event).filter(
        Event.uid == "5919D444-7C99-4687-A526-FC5D10091318").one()

    assert ev.status == 'confirmed'

    with open(absolute_path(FIXTURES + 'icloud_cancelled2.ics')) as fd:
        ics_data = fd.read()

    msg = add_fake_msg_with_calendar_part(
        db.session, default_account, ics_data)

    import_attached_events(db.session, default_account, msg)
    db.session.commit()

    ev = db.session.query(Event).filter(
        Event.uid == "5919D444-7C99-4687-A526-FC5D10091318").one()

    assert ev.status == 'cancelled'


def test_multiple_summaries(db, default_account):
    data = None
    with open(absolute_path(FIXTURES + 'multiple_summaries.ics')) as fd:
        data = fd.read()

    events = events_from_ics(default_account.namespace,
                             default_account.emailed_events_calendar, data)
    events = events['invites']
    assert len(events) == 1
    assert events[0].title == 'The Strokes - Is this it?'


def test_invalid_rsvp(db, default_account):
    # Test that we don't save an RSVP reply with an invalid id.
    data = None
    with open(absolute_path(FIXTURES + 'invalid_rsvp.ics')) as fd:
        data = fd.read()

    msg = add_fake_msg_with_calendar_part(
        db.session, default_account, data)

    import_attached_events(db.session, default_account, msg)
    db.session.commit()

    ev = db.session.query(Event).filter(
        Event.uid == "234252$cccc@nylas.com").all()

    assert len(ev) == 0


def test_rsvp_for_other_provider(db, default_account):
    # Test that we don't save RSVP replies which aren't to a Nylas
    # invite.
    data = None
    with open(absolute_path(FIXTURES + 'invalid_rsvp2.ics')) as fd:
        data = fd.read()

    msg = add_fake_msg_with_calendar_part(
        db.session, default_account, data)

    import_attached_events(db.session, default_account, msg)
    db.session.commit()

    ev = db.session.query(Event).filter(
        Event.uid == "234252cccc@google.com").all()

    assert len(ev) == 0
