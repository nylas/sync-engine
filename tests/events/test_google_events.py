import arrow
import json
import gevent
import mock
import pytest
import requests
from inbox.basicauth import AccessNotEnabledError
from inbox.events.google import GoogleEventsProvider, parse_event_response
from inbox.models import Calendar, Event
from inbox.models.event import RecurringEvent, RecurringEventOverride


def cmp_cal_attrs(calendar1, calendar2):
    return all(getattr(calendar1, attr) == getattr(calendar2, attr) for attr in
               ('name', 'uid', 'description', 'read_only'))


def cmp_event_attrs(event1, event2):
    for attr in ('title', 'description', 'location', 'start', 'end', 'all_day',
                 'owner', 'read_only', 'participants', 'recurrence'):
        if getattr(event1, attr) != getattr(event2, attr):
            print attr, getattr(event1, attr), getattr(event2, attr)
    return all(getattr(event1, attr) == getattr(event2, attr) for attr in
               ('title', 'description', 'location', 'start', 'end', 'all_day',
                'owner', 'read_only', 'participants', 'recurrence'))


def test_calendar_parsing():
    raw_response = [
        {
            'accessRole': 'owner',
            'backgroundColor': '#9a9cff',
            'colorId': '17',
            'defaultReminders': [{'method': 'popup', 'minutes': 30}],
            'etag': '"1425508164135000"',
            'foregroundColor': '#000000',
            'id': 'ben.bitdiddle2222@gmail.com',
            'kind': 'calendar#calendarListEntry',
            'notificationSettings': {
                'notifications': [
                    {'method': 'email', 'type': 'eventCreation'},
                    {'method': 'email', 'type': 'eventChange'},
                    {'method': 'email', 'type': 'eventCancellation'},
                    {'method': 'email', 'type': 'eventResponse'}
                ]
            },
            'primary': True,
            'selected': True,
            'summary': 'ben.bitdiddle2222@gmail.com',
            'timeZone': 'America/Los_Angeles'
        },
        {
            'accessRole': 'reader',
            'backgroundColor': '#f83a22',
            'colorId': '3',
            'defaultReminders': [],
            'description': 'Holidays and Observances in United States',
            'etag': '"1399416119263000"',
            'foregroundColor': '#000000',
            'id': 'en.usa#holiday@group.v.calendar.google.com',
            'kind': 'calendar#calendarListEntry',
            'selected': True,
            'summary': 'Holidays in United States',
            'timeZone': 'America/Los_Angeles'
        },
        {
            'defaultReminders': [],
            'deleted': True,
            'etag': '"1425952878772000"',
            'id': 'fg0s7qel95q86log75ilhhf12g@group.calendar.google.com',
            'kind': 'calendar#calendarListEntry'
        }
    ]
    expected_deletes = ['fg0s7qel95q86log75ilhhf12g@group.calendar.google.com']
    expected_updates = [
        Calendar(uid='ben.bitdiddle2222@gmail.com',
                 name='ben.bitdiddle2222@gmail.com',
                 description=None,
                 read_only=False),
        Calendar(uid='en.usa#holiday@group.v.calendar.google.com',
                 name='Holidays in United States',
                 description='Holidays and Observances in United States',
                 read_only=True)
    ]

    provider = GoogleEventsProvider(1, 1)
    provider._get_raw_calendars = mock.MagicMock(
        return_value=raw_response)
    deletes, updates = provider.sync_calendars()
    assert deletes == expected_deletes
    for obtained, expected in zip(updates, expected_updates):
        assert cmp_cal_attrs(obtained, expected)


def test_event_parsing():
    raw_response = [
        {
            'created': '2012-10-09T22:35:50.000Z',
            'creator': {
                'displayName': 'Eben Freeman',
                'email': 'freemaneben@gmail.com',
                'self': True
            },
            'end': {'dateTime': '2012-10-15T18:00:00-07:00'},
            'etag': '"2806773858144000"',
            'htmlLink': 'https://www.google.com/calendar/event?eid=FOO',
            'iCalUID': 'tn7krk4cekt8ag3pk6gapqqbro@google.com',
            'id': 'tn7krk4cekt8ag3pk6gapqqbro',
            'kind': 'calendar#event',
            'organizer': {
                'displayName': 'Eben Freeman',
                'email': 'freemaneben@gmail.com',
                'self': True
            },
            'attendees': [
                {'displayName': 'MITOC BOD',
                 'email': 'mitoc-bod@mit.edu',
                 'responseStatus': 'accepted'},
                {'displayName': 'Eben Freeman',
                 'email': 'freemaneben@gmail.com',
                 'responseStatus': 'accepted'}
            ],
            'reminders': {'useDefault': True},
            'recurrence': ['RRULE:FREQ=WEEKLY;UNTIL=20150209T075959Z;BYDAY=MO'],
            'sequence': 0,
            'start': {'dateTime': '2012-10-15T17:00:00-07:00'},
            'status': 'confirmed',
            'summary': 'BOD Meeting',
            'updated': '2014-06-21T21:42:09.072Z'
        },
        {
            'created': '2014-01-09T03:33:02.000Z',
            'creator': {
                'displayName': 'Holidays in United States',
                'email': 'en.usa#holiday@group.v.calendar.google.com',
                'self': True
            },
            'end': {u'date': '2014-06-16'},
            'etag': '"2778476764000000"',
            'htmlLink': 'https://www.google.com/calendar/event?eid=BAR',
            'iCalUID': '20140615_60o30dr564o30c1g60o30dr4ck@google.com',
            'id': '20140615_60o30dr564o30c1g60o30dr4ck',
            'kind': 'calendar#event',
            'organizer': {
                'displayName': 'Holidays in United States',
                'email': 'en.usa#holiday@group.v.calendar.google.com',
                'self': True
            },
            'sequence': 0,
            'start': {'date': '2014-06-15'},
            'status': 'confirmed',
            'summary': "Fathers' Day",
            'transparency': 'transparent',
            'updated': '2014-01-09T03:33:02.000Z',
            'visibility': 'public'
        },
        {
            'created': '2015-03-10T01:19:59.000Z',
            'creator': {
                'displayName': 'Ben Bitdiddle',
                'email': 'ben.bitdiddle2222@gmail.com',
                'self': True
            },
            'end': {u'date': '2015-03-11'},
            'etag': '"2851906839480000"',
            'htmlLink': 'https://www.google.com/calendar/event?eid=BAZ',
            'iCalUID': '3uisajkmdjqo43tfc3ig1l5hek@google.com',
            'id': '3uisajkmdjqo43tfc3ig1l5hek',
            'kind': 'calendar#event',
            'organizer': {
                'displayName': 'Ben Bitdiddle',
                'email': 'ben.bitdiddle2222@gmail.com',
                'self': True},
            'reminders': {u'useDefault': False},
            'sequence': 1,
            'start': {u'date': '2015-03-10'},
            'status': 'cancelled',
            'summary': 'TUESDAY',
            'transparency': 'transparent',
            'updated': '2015-03-10T02:10:19.740Z'
        }
    ]
    expected_deletes = ['3uisajkmdjqo43tfc3ig1l5hek']
    expected_updates = [
        RecurringEvent(uid='tn7krk4cekt8ag3pk6gapqqbro',
                       title='BOD Meeting',
                       description=None,
                       read_only=False,
                       start=arrow.get(2012, 10, 16, 0, 0, 0),
                       end=arrow.get(2012, 10, 16, 1, 0, 0),
                       all_day=False,
                       busy=True,
                       owner='Eben Freeman <freemaneben@gmail.com>',
                       recurrence=['RRULE:FREQ=WEEKLY;UNTIL=20150209T075959Z;BYDAY=MO'],
                       participants=[
                           {'email': 'mitoc-bod@mit.edu',
                            'name': 'MITOC BOD',
                            'status': 'yes',
                            'notes': None},
                           {'email': 'freemaneben@gmail.com',
                            'name': 'Eben Freeman',
                            'status': 'yes',
                            'notes': None}
                       ]),
        Event(uid='20140615_60o30dr564o30c1g60o30dr4ck',
              title="Fathers' Day",
              description=None,
              read_only=False,
              busy=False,
              start=arrow.get(2014, 06, 15),
              end=arrow.get(2014, 06, 15),
              all_day=True,
              owner='Holidays in United States <en.usa#holiday@group.v.calendar.google.com>',
              participants=[])
    ]

    provider = GoogleEventsProvider(1, 1)
    provider._get_raw_events = mock.MagicMock(
        return_value=raw_response)
    updates = provider.sync_events('uid', 1)

    # deleted events are actually only marked as
    # cancelled. Look for them in the updates stream.
    found_cancelled_event = False
    for event in updates:
        if event.uid in expected_deletes and event.status == 'cancelled':
            found_cancelled_event = True
            break

    assert found_cancelled_event

    for obtained, expected in zip(updates, expected_updates):
        print obtained, expected
        assert cmp_event_attrs(obtained, expected)


def test_handle_offset_all_day_events():
    raw_event = {
        'created': '2014-01-09T03:33:02.000Z',
        'creator': {
            'displayName': 'Ben Bitdiddle',
            'email': 'ben.bitdiddle2222@gmail.com',
            'self': True
        },
        'etag': '"2778476764000000"',
        'htmlLink': 'https://www.google.com/calendar/event?eid=BAR',
        'iCalUID': '20140615_60o30dr564o30c1g60o30dr4ck@google.com',
        'id': '20140615_60o30dr564o30c1g60o30dr4ck',
        'kind': 'calendar#event',
        'organizer': {
            'displayName': 'Ben Bitdiddle',
            'email': 'ben.bitdiddle2222@gmail.com',
            'self': True
        },
        'sequence': 0,
        'start': {'date': '2014-03-15'},
        'end': {u'date': '2014-03-15'},
        'status': 'confirmed',
        'summary': 'Ides of March',
        'transparency': 'transparent',
        'updated': '2014-01-09T03:33:02.000Z',
        'visibility': 'public'
    }
    expected = Event(uid='20140615_60o30dr564o30c1g60o30dr4ck',
                     title='Ides of March',
                     description=None,
                     read_only=False,
                     busy=False,
                     start=arrow.get(2014, 03, 15),
                     end=arrow.get(2014, 03, 15),
                     all_day=True,
                     owner='Ben Bitdiddle <ben.bitdiddle2222@gmail.com>',
                     participants=[])
    assert cmp_event_attrs(expected, parse_event_response(raw_event))


def test_pagination():
    first_response = requests.Response()
    first_response.status_code = 200
    first_response._content = json.dumps({
        'items': ['A', 'B', 'C'],
        'nextPageToken': 'CjkKKzlhb2tkZjNpZTMwNjhtZThllU'
    })
    second_response = requests.Response()
    second_response.status_code = 200
    second_response._content = json.dumps({
        'items': ['D', 'E']
    })

    requests.get = mock.Mock(side_effect=[first_response, second_response])
    provider = GoogleEventsProvider(1, 1)
    provider._get_access_token = mock.Mock(return_value='token')
    items = provider._get_resource_list('https://googleapis.com/testurl')
    assert items == ['A', 'B', 'C', 'D', 'E']


def test_handle_http_401():
    first_response = requests.Response()
    first_response.status_code = 401

    second_response = requests.Response()
    second_response.status_code = 200
    second_response._content = json.dumps({
        'items': ['A', 'B', 'C']
    })

    requests.get = mock.Mock(side_effect=[first_response, second_response])
    provider = GoogleEventsProvider(1, 1)
    provider._get_access_token = mock.Mock(return_value='token')
    items = provider._get_resource_list('https://googleapis.com/testurl')
    assert items == ['A', 'B', 'C']
    # Check that we actually refreshed the access token
    assert len(provider._get_access_token.mock_calls) == 2


def test_handle_quota_exceeded():
    first_response = requests.Response()
    first_response.status_code = 403
    first_response._content = json.dumps({
        'error': {
            'errors': [
                {'domain': 'usageLimits',
                 'reason': 'userRateLimitExceeded',
                 'message': 'User Rate Limit Exceeded'}
            ],
            'code': 403,
            'message': 'User Rate Limit Exceeded'
        }
    })

    second_response = requests.Response()
    second_response.status_code = 200
    second_response._content = json.dumps({
        'items': ['A', 'B', 'C']
    })

    requests.get = mock.Mock(side_effect=[first_response, second_response])
    gevent.sleep = mock.Mock()
    provider = GoogleEventsProvider(1, 1)
    provider._get_access_token = mock.Mock(return_value='token')
    items = provider._get_resource_list('https://googleapis.com/testurl')
    # Check that we slept, then retried.
    gevent.sleep.assert_called_once_with(30)
    assert items == ['A', 'B', 'C']


def test_handle_internal_server_error():
    first_response = requests.Response()
    first_response.status_code = 503

    second_response = requests.Response()
    second_response.status_code = 200
    second_response._content = json.dumps({
        'items': ['A', 'B', 'C']
    })

    requests.get = mock.Mock(side_effect=[first_response, second_response])
    gevent.sleep = mock.Mock()
    provider = GoogleEventsProvider(1, 1)
    provider._get_access_token = mock.Mock(return_value='token')
    items = provider._get_resource_list('https://googleapis.com/testurl')
    # Check that we slept, then retried.
    gevent.sleep.assert_called_once_with(30)
    assert items == ['A', 'B', 'C']


def test_handle_api_not_enabled():
    response = requests.Response()
    response.status_code = 403
    response._content = json.dumps({
        'error': {
            'code': 403,
            'message': 'Access Not Configured.',
            'errors': [
                {'domain': 'usageLimits', 'message': 'Access Not Configured',
                  'reason': 'accessNotConfigured',
                 'extendedHelp': 'https://console.developers.google.com'}
            ]
        }
    })

    requests.get = mock.Mock(return_value=response)
    provider = GoogleEventsProvider(1, 1)
    provider._get_access_token = mock.Mock(return_value='token')
    with pytest.raises(AccessNotEnabledError):
        provider._get_resource_list('https://googleapis.com/testurl')


def test_handle_other_errors():
    response = requests.Response()
    response.status_code = 403
    response._content = "This is not the JSON you're looking for"
    requests.get = mock.Mock(return_value=response)
    provider = GoogleEventsProvider(1, 1)
    provider._get_access_token = mock.Mock(return_value='token')
    with pytest.raises(requests.exceptions.HTTPError):
        provider._get_resource_list('https://googleapis.com/testurl')

    response = requests.Response()
    response.status_code = 404
    requests.get = mock.Mock(return_value=response)
    provider = GoogleEventsProvider(1, 1)
    provider._get_access_token = mock.Mock(return_value='token')
    with pytest.raises(requests.exceptions.HTTPError):
        provider._get_resource_list('https://googleapis.com/testurl')


def test_recurrence_creation():
    event = {
        'created': '2012-10-09T22:35:50.000Z',
        'creator': {
            'displayName': 'Eben Freeman',
            'email': 'freemaneben@gmail.com',
            'self': True
        },
        'end': {'dateTime': '2012-10-15T18:00:00-07:00'},
        'etag': '"2806773858144000"',
        'htmlLink': 'https://www.google.com/calendar/event?eid=FOO',
        'iCalUID': 'tn7krk4cekt8ag3pk6gapqqbro@google.com',
        'id': 'tn7krk4cekt8ag3pk6gapqqbro',
        'kind': 'calendar#event',
        'organizer': {
            'displayName': 'Eben Freeman',
            'email': 'freemaneben@gmail.com',
            'self': True
        },
        'attendees': [
            {'displayName': 'MITOC BOD',
             'email': 'mitoc-bod@mit.edu',
             'responseStatus': 'accepted'},
            {'displayName': 'Eben Freeman',
             'email': 'freemaneben@gmail.com',
             'responseStatus': 'accepted'}
        ],
        'reminders': {'useDefault': True},
        'recurrence': ['RRULE:FREQ=WEEKLY;UNTIL=20150209T075959Z;BYDAY=MO',
                       'EXDATE;TZID=America/Los_Angeles:20150208T010000'],
        'sequence': 0,
        'start': {'dateTime': '2012-10-15T17:00:00-07:00',
                  'timeZone': 'America/Los_Angeles'},
        'status': 'confirmed',
        'summary': 'BOD Meeting',
        'updated': '2014-06-21T21:42:09.072Z'
    }
    event = parse_event_response(event)
    assert isinstance(event, RecurringEvent)
    assert event.rrule == 'RRULE:FREQ=WEEKLY;UNTIL=20150209T075959Z;BYDAY=MO'
    assert event.exdate == 'EXDATE;TZID=America/Los_Angeles:20150208T010000'
    assert event.until == arrow.get(2015, 02, 9, 7, 59, 59)
    assert event.start_timezone == 'America/Los_Angeles'


def test_override_creation():
    event = {
        'created': '2012-10-09T22:35:50.000Z',
        'creator': {
            'displayName': 'Eben Freeman',
            'email': 'freemaneben@gmail.com',
            'self': True
        },
        'end': {'dateTime': '2012-10-22T19:00:00-07:00'},
        'etag': '"2806773858144000"',
        'htmlLink': 'https://www.google.com/calendar/event?eid=FOO',
        'iCalUID': 'tn7krk4cekt8ag3pk6gapqqbro@google.com',
        'id': 'tn7krk4cekt8ag3pk6gapqqbro_20121022T170000Z',
        'kind': 'calendar#event',
        'organizer': {
            'displayName': 'Eben Freeman',
            'email': 'freemaneben@gmail.com',
            'self': True
        },
        'attendees': [
            {'displayName': 'MITOC BOD',
             'email': 'mitoc-bod@mit.edu',
             'responseStatus': 'accepted'},
            {'displayName': 'Eben Freeman',
             'email': 'freemaneben@gmail.com',
             'responseStatus': 'accepted'}
        ],
        'originalStartTime': {
            'dateTime': '2012-10-22T17:00:00-07:00',
            'timeZone': 'America/Los_Angeles'
        },
        'recurringEventId': 'tn7krk4cekt8ag3pk6gapqqbro',
        'reminders': {'useDefault': True},
        'sequence': 0,
        'start': {'dateTime': '2012-10-22T18:00:00-07:00',
                  'timeZone': 'America/Los_Angeles'},
        'status': 'confirmed',
        'summary': 'BOD Meeting',
        'updated': '2014-06-21T21:42:09.072Z'
    }
    event = parse_event_response(event)
    assert isinstance(event, RecurringEventOverride)
    assert event.master_event_uid == 'tn7krk4cekt8ag3pk6gapqqbro'
    assert event.original_start_time == arrow.get(2012, 10, 23, 00, 00, 00)


def test_cancelled_override_creation():
    # With showDeleted=True, we receive cancelled events (including instances
    # of recurring events) as full event objects, with status = 'cancelled'.
    # Test that we save this as a RecurringEventOverride rather than trying
    # to delete the UID.
    raw_response = [{
        'created': '2012-10-09T22:35:50.000Z',
        'creator': {
            'displayName': 'Eben Freeman',
            'email': 'freemaneben@gmail.com',
            'self': True
        },
        'end': {'dateTime': '2012-10-22T19:00:00-07:00'},
        'etag': '"2806773858144000"',
        'htmlLink': 'https://www.google.com/calendar/event?eid=FOO',
        'iCalUID': 'tn7krk4cekt8ag3pk6gapqqbro@google.com',
        'id': 'tn7krk4cekt8ag3pk6gapqqbro_20121022T170000Z',
        'kind': 'calendar#event',
        'organizer': {
            'displayName': 'Eben Freeman',
            'email': 'freemaneben@gmail.com',
            'self': True
        },
        'attendees': [
            {'displayName': 'MITOC BOD',
             'email': 'mitoc-bod@mit.edu',
             'responseStatus': 'accepted'},
            {'displayName': 'Eben Freeman',
             'email': 'freemaneben@gmail.com',
             'responseStatus': 'accepted'}
        ],
        'originalStartTime': {
            'dateTime': '2012-10-22T17:00:00-07:00',
            'timeZone': 'America/Los_Angeles'
        },
        'recurringEventId': 'tn7krk4cekt8ag3pk6gapqqbro',
        'reminders': {'useDefault': True},
        'sequence': 0,
        'start': {'dateTime': '2012-10-22T18:00:00-07:00',
                  'timeZone': 'America/Los_Angeles'},
        'status': 'cancelled',
        'summary': 'BOD Meeting',
    }]

    provider = GoogleEventsProvider(1, 1)
    provider._get_raw_events = mock.MagicMock(
        return_value=raw_response)
    updates = provider.sync_events('uid', 1)
    assert updates[0].cancelled is True
