"""Utilities for filtering message entries in the transaction log."""
import itertools
import re


class TransactionDataFilter(object):
    """Filter based on the given parameters.
    String parameters that begin and end with '/' are interpreted as Python
    regular expressions and matched against the beginning of a string.
    Otherwise exact string matching is applied. Callers using backslashes in
    regexen must either escape them or pass the argument as a raw string (e.g.,
    r'\W+').

    Parameters
    ----------
    email: string or unicode
        Match a name or email address in any of the from, to, cc or bcc fields.
    to_addr, from_addr, cc_addr, bcc_addr: string or unicode
        Match a name or email address in the to, from, cc or bcc fields.
    folder_name: string or unicode
        Match messages contained in the given folder.
    filename: string or unicode
        Match messages that have an attachment matching the given filename.
    thread: integer
        Match messages with given public thread id.
    started_before: datetime.datetime
        Match threads whose first message is dated before the given time.
    started_after: datetime.datetime
        Match threads whose first message is dated after the given time.
    last_message_before: datetime.datetime
        Match threads whose last message is dated before the given time.
    last_message_after: datetime.datetime
        Match threads whose last message is dated after the given time.


    Raises
    ------
    ValueError: If an invalid regex is supplied as a parameter.

    Examples
    --------
    >>> msg = {
    ...    'subject': 'Microwave ovens',
    ...    'from_addr': [['Richard Stallman', 'rms@gnu.org']]
    ... }
    >>> filter = TransactionDataFilter(from_addr='/.*Stallman/')
    >>> filter.match(msg)
    True
    >>> filter = TransactionDataFilter(from_addr='/.*Stallman/',
    ...                 subject='Mice')
    >>> filter.match(msg)
    False
    """

    def __init__(self, subject=None, email=None, to_addr=None, from_addr=None,
                 cc_addr=None, bcc_addr=None, folder=None, started_before=None,
                 started_after=None, last_message_before=None,
                 last_message_after=None, thread=None, filename=None):
        self.filters = []
        self.add_string_filter(subject, get_subject)
        self.add_string_filter(to_addr, get_to)
        self.add_string_filter(from_addr, get_from)
        self.add_string_filter(cc_addr, get_cc)
        self.add_string_filter(bcc_addr, get_bcc)
        self.add_string_filter(folder, get_folders)
        self.add_string_filter(email, get_emails)
        self.add_string_filter(filename, get_filenames)

        if thread is not None:
            self.filters.append(lambda message:
                                message['thread']['id'] == thread)

        if started_before is not None:
            self.filters.append(
                lambda message: (message['thread']['subject_date'] <
                                 started_before))

        if started_after is not None:
            self.filters.append(
                lambda message: (message['thread']['subject_date'] >
                                 started_after))

        if last_message_before is not None:
            self.filters.append(
                lambda message: (message['thread']['recent_date'] <
                                 last_message_before))

        if last_message_after is not None:
            self.filters.append(
                lambda message: (message['thread']['recent_date'] >
                                 last_message_after))

    def add_string_filter(self, filter_string, selector):
        if filter_string is None:
            return

        if filter_string.startswith('/') and filter_string.endswith('/'):
            try:
                regex = re.compile(filter_string[1:-1])
            except re.error:
                raise ValueError('Invalid regex argument')
            predicate = regex.match
        else:
            predicate = lambda candidate: filter_string == candidate

        def matcher(message):
            field = selector(message)
            if isinstance(field, basestring):
                if not predicate(field):
                    return False
            else:
                if not any(predicate(elem) for elem in field):
                    return False
            return True

        self.filters.append(matcher)

    def match(self, message_dict):
        """Returns True if and only if the given message matches all filtering
        criteria."""
        return all(filter(message_dict) for filter in self.filters)


# Utility functions for creating filter objects.


def get_subject(message):
    return message['subject']


def get_folders(message):
    return message['thread']['folders']


def flatten_field(field):
    """Given a list of (name, email) pairs, return an iterator over all
    the names and emails. If field is None, return the empty iterator.

    Parameters
    ----------
    field: list of iterables

    Returns
    -------
    iterable

    Example
    -------
    >>> list(flatten_field([('Name', 'email'),
    ...                     ('Another Name', 'another email')]))
    ['Name', 'email', 'Another Name', 'another email']
    """
    return itertools.chain(*field) if field is not None else ()


def get_to(message):
    return flatten_field(message['to_addr'])


def get_from(message):
    return flatten_field(message['from_addr'])


def get_cc(message):
    return flatten_field(message['cc_addr'])


def get_bcc(message):
    return flatten_field(message['bcc_addr'])


def get_emails(message):
    return itertools.chain(func(message) for func in
                           (get_to, get_from, get_cc, get_bcc))


def get_filenames(message):
    return (block['filename'] for block in message['blocks']
            if block['filename'] is not None)
