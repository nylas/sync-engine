import arrow
from datetime import timedelta

from inbox.models.when import (Time, TimeSpan, Date, DateSpan, parse_as_when,
                               parse_utc)
from inbox.models.event import time_parse
from inbox.events.util import (google_to_event_time, parse_google_time,
                               parse_datetime)


def test_when_time():
    start_time = arrow.get('2014-09-30T15:34:00.000-07:00')
    time = {'time': start_time.timestamp}
    ts = parse_as_when(time)
    assert isinstance(ts, Time)
    assert ts.start == start_time.to('utc')
    assert ts.end == start_time.to('utc')
    assert not ts.spanning
    assert not ts.all_day
    assert ts.is_time
    assert not ts.is_date
    assert ts.delta == timedelta(hours=0)


def test_when_timespan():
    start_time = arrow.get('2014-09-30T15:34:00.000-07:00')
    end_time = arrow.get('2014-09-30T16:34:00.000-07:00')
    timespan = {'start_time': start_time.timestamp,
                'end_time': end_time.timestamp}
    ts = parse_as_when(timespan)
    assert isinstance(ts, TimeSpan)
    assert ts.start == start_time.to('utc')
    assert ts.end == end_time.to('utc')
    assert ts.spanning
    assert not ts.all_day
    assert ts.is_time
    assert not ts.is_date
    assert ts.delta == timedelta(hours=1)


def test_when_date():
    start_date = arrow.get('2014-09-30')
    date = {'date': start_date.format('YYYY-MM-DD')}
    ts = parse_as_when(date)
    assert isinstance(ts, Date)
    assert ts.start == start_date
    assert ts.end == start_date
    assert not ts.spanning
    assert ts.all_day
    assert not ts.is_time
    assert ts.is_date
    assert ts.delta == timedelta(days=0)


def test_when_datespan():
    start_date = arrow.get('2014-09-30')
    end_date = arrow.get('2014-10-01')
    datespan = {'start_date': start_date.format('YYYY-MM-DD'),
                'end_date': end_date.format('YYYY-MM-DD')}
    ts = parse_as_when(datespan)
    assert isinstance(ts, DateSpan)
    assert ts.start == start_date
    assert ts.end == end_date
    assert ts.spanning
    assert ts.all_day
    assert not ts.is_time
    assert ts.is_date
    assert ts.delta == timedelta(days=1)


def test_when_spans_arent_spans():
    # If start and end are the same, don't create a Span object
    start_date = arrow.get('2014-09-30')
    end_date = arrow.get('2014-09-30')
    datespan = {'start_date': start_date.format('YYYY-MM-DD'),
                'end_date': end_date.format('YYYY-MM-DD')}
    ts = parse_as_when(datespan)
    assert isinstance(ts, Date)

    start_time = arrow.get('2014-09-30T15:34:00.000-07:00')
    end_time = arrow.get('2014-09-30T15:34:00.000-07:00')
    timespan = {'start_time': start_time.timestamp,
                'end_time': end_time.timestamp}
    ts = parse_as_when(timespan)
    assert isinstance(ts, Time)


def test_parse_datetime():
    t = '20140104T102030Z'
    dt = parse_datetime(t)
    assert dt == arrow.get(2014, 01, 04, 10, 20, 30)

    t = '2014-01-15T17:00:00-05:00'
    dt = parse_datetime(t)
    assert dt == arrow.get(2014, 01, 15, 22, 00, 00)

    t = None
    dt = parse_datetime(t)
    assert dt is None

    t = 1426008600
    dt = parse_datetime(t)
    assert dt == arrow.get(2015, 03, 10, 17, 30, 00)


def test_time_parse():
    t = 1426008600
    validated = parse_utc(t)
    stored = time_parse(t)

    assert validated.naive == stored

    t = str(1426008600)
    validated = parse_utc(t)
    stored = time_parse(t)

    assert validated.naive == stored


def test_parse_google_time():
    t = {'dateTime': '2012-10-15T17:00:00-07:00',
         'timeZone': 'America/Los_Angeles'}
    gt = parse_google_time(t)
    assert gt.to('utc') == arrow.get(2012, 10, 16, 00, 00, 00)

    t = {'dateTime': '2012-10-15T13:00:00+01:00'}
    gt = parse_google_time(t)
    assert gt.to('utc') == arrow.get(2012, 10, 15, 12, 00, 00)

    t = {'date': '2012-10-15'}
    gt = parse_google_time(t)
    assert gt == arrow.get(2012, 10, 15)


def test_google_to_event_time():
    start = {'dateTime': '2012-10-15T17:00:00-07:00',
             'timeZone': 'America/Los_Angeles'}
    end = {'dateTime': '2012-10-15T17:25:00-07:00',
           'timeZone': 'America/Los_Angeles'}
    event_time = google_to_event_time(start, end)
    assert event_time.start == arrow.get(2012, 10, 16, 00, 00, 00)
    assert event_time.end == arrow.get(2012, 10, 16, 00, 25, 00)
    assert event_time.all_day is False

    start = {'date': '2012-10-15'}
    end = {'date': '2012-10-16'}
    event_time = google_to_event_time(start, end)
    assert event_time.start == arrow.get(2012, 10, 15)
    assert event_time.end == arrow.get(2012, 10, 15)
    assert event_time.all_day is True
