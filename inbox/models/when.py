from datetime import datetime
from dateutil.parser import parse as date_parse


def parse_as_when(raw):
    """Tries to parse a dictionary into a corresponding Date, DateSpan,
    Time, or TimeSpan instance.

    Raises
    -------
    ValueError
    """
    keys_for_type = {
        ('start_time', 'end_time'): TimeSpan,
        ('time', ): Time,
        ('start_date', 'end_date'): DateSpan,
        ('date', ): Date
    }
    given_keys = tuple(set(raw.keys()) - set('object'))
    when_type = keys_for_type.get(given_keys)
    if when_type is None:
        raise ValueError("When object had invalid keys.")
    return when_type.parse(raw)


class When(object):
    pass


class Time(When):
    @classmethod
    def parse(cls, raw):
        try:
            time = datetime.utcfromtimestamp(raw['time'])
        except (ValueError, TypeError):
            raise ValueError("'time' parameter invalid.")
        return cls(time)

    def __init__(self, time):
        self.time = time


class TimeSpan(When):
    @classmethod
    def parse(cls, raw):
        try:
            start_time = datetime.utcfromtimestamp(raw['start_time'])
            end_time = datetime.utcfromtimestamp(raw['end_time'])
        except (ValueError, TypeError):
            raise ValueError("'start_time' or 'end_time' invalid.")
        if start_time >= end_time:
            raise ValueError("'start_date' must be < 'end_date'.")
        return cls(start_time, end_time)

    def __init__(self, start, end):
        self.start_time = start
        self.end_time = end


class Date(When):
    @classmethod
    def parse(cls, raw):
        try:
            date = date_parse(raw['date'])
        except (AttributeError, ValueError, TypeError):
            raise ValueError("'date' parameter invalid.")
        return cls(date)

    def __init__(self, date):
        self.date = date


class DateSpan(When):
    @classmethod
    def parse(cls, raw):
        try:
            start_date = date_parse(raw['start_date'])
            end_date = date_parse(raw['end_date'])
        except (AttributeError, ValueError, TypeError):
            raise ValueError("'start_date' or 'end_date' invalid.")
        if start_date >= end_date:
            raise ValueError("'start_date' must be < 'end_date'.")
        return cls(start_date, end_date)

    def __init__(self, start, end):
        self.start_date = start
        self.end_date = end
