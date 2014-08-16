import dateutil.parser as date_parser
from dateutil import tz


class MalformedEventError(Exception):
    pass


def parse_datetime(date):
    if not date:
        raise MalformedEventError()
    try:
        dt = date_parser.parse(date)
        return dt.astimezone(tz.gettz('UTC')).replace(tzinfo=None)
    except ValueError:
        raise MalformedEventError()
