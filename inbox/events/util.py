import arrow
from dateutil.parser import parse
from collections import namedtuple
from inbox.models.when import parse_as_when


# TODO(emfree) remove (currently used in other repos)
class MalformedEventError(Exception):
    pass


def parse_datetime(datetime):
    # returns a UTC-aware datetime as an Arrow object.
    # to access the `datetime` object: `obj.datetime`
    # to convert to a naive datetime: `obj.naive`
    # http://crsmithdev.com/arrow/
    if datetime is not None:
        if isinstance(datetime, int):
            return arrow.get(datetime).to('utc')
        return arrow.get(parse(datetime)).to('utc')


def parse_rrule_datetime(datetime, tzinfo=None):
    # format: 20140904T133000Z (datetimes) or 20140904 (dates)
    if datetime[-1] == 'Z':
        tzinfo = 'UTC'
        datetime = datetime[:-1]
    if len(datetime) == 8:
        dt = arrow.get(datetime, 'YYYYMMDD').to('utc')
    else:
        dt = arrow.get(datetime, 'YYYYMMDDTHHmmss')
    if tzinfo and tzinfo != 'UTC':
        dt = arrow.get(dt.datetime, tzinfo)
    return dt

EventTime = namedtuple('EventTime', ['start', 'end', 'all_day'])


def when_to_event_time(raw):
    when = parse_as_when(raw)
    return EventTime(when.start, when.end, when.all_day)


def parse_google_time(d):
    # google dictionaries contain either 'date' or 'dateTime' & 'timeZone'
    # 'dateTime' is in ISO format so is UTC-aware, 'date' is just a date
    for key, dt in d.iteritems():
        if key != 'timeZone':
            return arrow.get(dt)


def google_to_event_time(start_raw, end_raw):
    start = parse_google_time(start_raw)
    end = parse_google_time(end_raw)
    if 'date' in start_raw:
        # Google all-day events end a 'day' later than they should
        end = end.replace(days=-1)
        d = {'start_date': start, 'end_date': end}
    else:
        d = {'start_time': start, 'end_time': end}

    event_time = when_to_event_time(d)

    return event_time
