import pytest

from inbox.models import Account
from inbox.events.google import GoogleEventsProvider
from inbox.events.google import MalformedEventError
from inbox.events.ical import events_from_ics

ACCOUNT_ID = 1


@pytest.fixture(scope='function')
def google_events_provider(config, db):
    return GoogleEventsProvider(ACCOUNT_ID)


def test_cancelled_event(google_events_provider):
    """Test that the parser gracefully handles cancelled dates."""
    cal_info = {}
    event = {u'status': u'cancelled', u'kind':
             u'calendar#event',
             u'originalStartTime':
             {u'dateTime': u'2011-10-06T23:31:00-07:00'},
             u'etag': u'"2632026776000000"',
             u'recurringEventId': u'f3jukdd49bc36smsui4rb35n18',
             u'id': u'f3jukdd49bc36smsui4rb35n18_20111007T063100Z'}
    with pytest.raises(MalformedEventError):
        google_events_provider.parse_event(event, cal_info)


def test_malformed_event(google_events_provider):
    """Test that the parser gracefully handles malformed events."""
    cal_info = {}
    event = {u'originalStartTime':
             {u'dateTime': u'2011-10-06T23:31:00-07:00'},
             u'reminders': {u'useDefault': False},
             u'start': {u'dateTime': None},
             u'end': {u'dateTime': u'2014-08-11T13:00:00-07:00'},
             u'etag': u'"2632026776000000"',
             u'recurringEventId': u'f3jukdd49bc36smsui4rb35n18',
             u'id': u'f3jukdd49bc36smsui4rb35n18_20111007T063100Z'}
    with pytest.raises(MalformedEventError):
        google_events_provider.parse_event(event, cal_info)

    event['start'] = {'dateTime': 'asdf'}
    with pytest.raises(MalformedEventError):
        google_events_provider.parse_event(event, cal_info)


def test_no_reminders(google_events_provider):
    """Test that the parser gracefully handles events with no reminders."""
    cal_info = {u'kind': u'calendar#events',
                u'defaultReminders': [{u'minutes': 30, u'method': u'popup'}],
                u'updated': u'2014-08-11T19:38:10.004Z',
                u'summary': u'fakeemail@gmail.com',
                u'etag': u'"1407785890004000"',
                u'nextSyncToken': u'CKD4ko_7i8ACEKD4ko_7i8ACGAU=',
                u'timeZone': u'America/Los_Angeles',
                u'accessRole': u'owner'}
    event = {u'status': u'confirmed',
             u'kind': u'calendar#event',
             u'end': {u'dateTime': u'2014-08-11T13:00:00-07:00'},
             u'description': u'Our usual lunch destination.',
             u'created': u'2014-08-11T19:38:09.000Z',
             u'iCalUID': u't0msu19ehpo48tp2pek4j2kh70@google.com',
             u'reminders': {u'useDefault': False},
             u'htmlLink': u'',
             u'sequence': 0,
             u'updated': u'2014-08-11T19:38:09.938Z',
             u'summary': u'Lunch',
             u'start': {u'dateTime': u'2014-08-11T12:00:00-07:00'},
             u'etag': u'"2815571779793000"',
             u'location': u'Stable Cafe',
             u'organizer': {u'self': True,
                            u'displayName': u'Ben Bitdiddle',
                            u'email': u'fakeemail@gmail.com'},
             u'creator': {u'self': True,
                          u'displayName': u'Ben Bitdiddle',
                          u'email': u'fakeemail@gmail.com'},
             u'id': u't0msu19ehpo48tp2pek4j2kh70'}
    google_events_provider.parse_event(event, cal_info)


def test_long_eventid(google_events_provider):
    """Test that the parser gracefully handles events with long ids."""
    long_id = (u'_60q30c1g60o30e1i60o4ac1g60rj8gpl88rj2c1h84s34h9g60s30c1g60o3'
               '0c1g6so3chhm6ko30e258cs46ghg64o30c1g60o30c1g60o30c1g60o32c1g60'
               'o30c1g88s32d9k751j0ga475144ghk6ks48ha468o42ha565144h9n8cp0')
    cal_info = {}
    cal_info = {u'kind': u'calendar#events',
                u'defaultReminders': [{u'minutes': 30, u'method': u'popup'}],
                u'updated': u'2014-08-11T19:38:10.004Z',
                u'summary': u'fakeemail@gmail.com',
                u'etag': u'"1407785890004000"',
                u'nextSyncToken': u'CKD4ko_7i8ACEKD4ko_7i8ACGAU=',
                u'timeZone': u'America/Los_Angeles',
                u'accessRole': u'owner'}
    event = {u'status': u'confirmed',
             u'kind': u'calendar#event',
             u'end': {u'dateTime': u'2014-08-11T13:00:00-07:00'},
             u'description': u'Our usual lunch destination.',
             u'created': u'2014-08-11T19:38:09.000Z',
             u'iCalUID': u't0msu19ehpo48tp2pek4j2kh70@google.com',
             u'reminders': {u'useDefault': False},
             u'htmlLink': u'',
             u'sequence': 0,
             u'updated': u'2014-08-11T19:38:09.938Z',
             u'summary': u'Lunch',
             u'start': {u'dateTime': u'2014-08-11T12:00:00-07:00'},
             u'etag': u'"2815571779793000"',
             u'location': u'Stable Cafe',
             u'organizer': {u'self': True,
                            u'displayName': u'Ben Bitdiddle',
                            u'email': u'fakeemail@gmail.com'},
             u'creator': {u'self': True,
                          u'displayName': u'Ben Bitdiddle',
                          u'email': u'fakeemail@gmail.com'},
             u'id': long_id}
    google_events_provider.parse_event(event, cal_info)


def test_invalid_ical(db):
    with pytest.raises(MalformedEventError):
        account = db.session.query(Account).filter_by(id=ACCOUNT_ID).first()
        events_from_ics(account.namespace,
                        account.default_calendar, "asdf")
