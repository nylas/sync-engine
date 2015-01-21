import dateutil.parser
import dateutil.tz


# TODO(emfree) remove (currently used in other repos)
class MalformedEventError(Exception):
    pass


def parse_datetime(datetime):
    dt = dateutil.parser.parse(datetime)
    if dt.tzinfo is not None:
        # Convert to naive datetime representing UTC.
        return dt.astimezone(dateutil.tz.gettz('UTC')).replace(tzinfo=None)
    else:
        return dt
