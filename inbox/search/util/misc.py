import time
import calendar


def process_datetime(source):
    """
    Convert the default string datetime format returned by Elasticsearch
    to Unix timestamp format.

    So for example, 2014-04-03T02:19:42 is converted to 1396491582.

    """
    for field in source.iterkeys():
        if field in ['date', 'last_message_timestamp',
                     'first_message_timestamp']:
            datestring = source[field]
            source[field] = calendar.timegm(
                time.strptime(datestring, '%Y-%m-%dT%H:%M:%S'))

    return source
