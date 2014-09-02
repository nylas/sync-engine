"""Utilities for validating user input to the API."""
from datetime import datetime
from inbox.models.when import parse_as_when
from flask.ext.restful import reqparse
from sqlalchemy.orm.exc import NoResultFound
from inbox.models import Account, Calendar, Tag, Thread, Part

MAX_LIMIT = 1000


class InputError(Exception):
    """Raised when bad user input is processed."""
    def __init__(self, error):
        self.error = error

    def __str__(self):
        return self.error


class ValidatableArgument(reqparse.Argument):
    def handle_validation_error(self, error):
        raise InputError(str(error))


# Custom parameter types

def bounded_str(value, key):
    if len(value) > 255:
        raise ValueError('Value {} for {} is too long'.format(value, key))
    return value


def limit(value):
    try:
        value = int(value)
    except ValueError:
        raise ValueError('Limit parameter must be an integer.')
    if value < 0:
        raise ValueError('Limit parameter must be nonnegative.')
    if value > MAX_LIMIT:
        raise ValueError('Cannot request more than {} resources at once.'.
                         format(MAX_LIMIT))
    return value


def valid_public_id(value):
    try:
        # raise ValueError on malformed public ids
        # raise TypeError if an integer is passed in
        int(value, 36)
    except (TypeError, ValueError):
        raise InputError('Invalid id {}'.format(value))
    return value


def timestamp(value, key):
    try:
        return datetime.utcfromtimestamp(int(value))
    except ValueError:
        raise ValueError('Invalid timestamp value {} for {}'.
                         format(value, key))


def boolean(value, key):
    if value.lower() in ('false', '0'):
        return False
    elif value.lower() in ('true', '1'):
        return True
    raise ValueError('Invalid boolean value {} for {}'.
                     format(value, key))


def strict_parse_args(parser, raw_args):
    """Wrapper around parser.parse_args that raises a ValueError if unexpected
    arguments are present."""
    args = parser.parse_args()
    unexpected_params = (set(raw_args) - {allowed_arg.name for allowed_arg in
                                          parser.args})
    if unexpected_params:
        raise InputError('Unexpected query parameters {}'.
                         format(unexpected_params))
    return args


def get_tags(tag_public_ids, namespace_id, db_session):
    tags = set()
    if tag_public_ids is None:
        return tags
    if not isinstance(tag_public_ids, list):
        raise InputError('{} is not a list of tag ids'.format(tag_public_ids))
    for tag_public_id in tag_public_ids:
        # Validate public id before querying with it
        valid_public_id(tag_public_id)
        try:
            # We're trading a bit of performance for more meaningful error
            # messages here by looking these up one-by-one.
            tag = db_session.query(Tag). \
                filter(Tag.namespace_id == namespace_id,
                       Tag.public_id == tag_public_id,
                       Tag.user_created).one()
            tags.add(tag)
        except NoResultFound:
            raise InputError('Invalid tag public id {}'.format(tag_public_id))
    return tags


def get_attachments(parts_public_ids, namespace_id, db_session):
    attachments = set()
    if parts_public_ids is None:
        return attachments
    if not isinstance(parts_public_ids, list):
        raise InputError('{} is not a list of block ids'.
                         format(parts_public_ids))
    for part_public_id in parts_public_ids:
        # Validate public ids before querying with them
        valid_public_id(part_public_id)
        try:
            part = db_session.query(Part). \
                filter(Part.public_id == part_public_id,
                       Part.namespace_id == namespace_id).one()
            # In the future we may consider discovering the filetype from the
            # data by using #magic.from_buffer(data, mime=True))
            attachments.add(part)
        except NoResultFound:
            raise InputError('Invalid part public id {}'.
                             format(part_public_id))
    return attachments


def get_thread(thread_public_id, namespace_id, db_session):
    if thread_public_id is None:
        return None
    valid_public_id(thread_public_id)
    try:
        return db_session.query(Thread). \
            filter(Thread.public_id == thread_public_id,
                   Thread.namespace_id == namespace_id).one()
    except NoResultFound:
        raise InputError('Invalid thread public id {}'.
                         format(thread_public_id))


def get_calendar(calendar_public_id, namespace, db_session):
    if calendar_public_id is None:
        account = db_session.query(Account).filter(
            Account.id == namespace.account_id).one()
        return account.default_calendar
    valid_public_id(calendar_public_id)
    try:
        return db_session.query(Calendar). \
            filter(Calendar.public_id == calendar_public_id,
                   Calendar.account_id == namespace.account_id).one()
    except NoResultFound:
        raise InputError('Invalid calendar public id {}'.
                         format(calendar_public_id))


def valid_when(when):
    try:
        parse_as_when(when)
    except ValueError as e:
        raise InputError(str(e))


def valid_event(event):
    if 'when' not in event:
        raise InputError("Must specify 'when' when creating an event.")

    valid_when(event['when'])

    participants = event.get('participants', [])
    for p in participants:
        if 'email' not in p:
            raise InputError("'participants' must must have email")
        if 'status' in p:
            if p['status'] not in ('yes', 'no', 'maybe', 'noreply'):
                raise InputError("'participants' status must be one of: "
                                 "yes, no, maybe, noreply")


def valid_event_update(event, namespace, db_session):
    if 'when' in event:
        valid_when(event['when'])

    if 'busy' in event and not isinstance(event.get('busy'), bool):
        raise InputError('\'busy\' must be true or false')

    calendar = get_calendar(event.get('calendar_id'),
                            namespace, db_session)
    if calendar and calendar.read_only:
        raise InputError("Cannot move event to read_only calendar.")

    participants = event.get('participants', [])
    for p in participants:
        if 'email' not in p:
            raise InputError("'participants' must must have email")
        if 'status' in p:
            if p['status'] not in ('yes', 'no', 'maybe', 'noreply'):
                raise InputError("'participants' status must be one of: "
                                 "yes, no, maybe, noreply")


def valid_event_action(action):
    if action not in ['rsvp']:
        raise InputError('Invalid event action: {}'.format(action))
    return action


def valid_rsvp(rsvp):
    if rsvp not in ['yes', 'no', 'maybe']:
        raise InputError('Invalid rsvp: {}'.format(rsvp))
    return rsvp
