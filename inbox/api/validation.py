"""Utilities for validating user input to the API."""
from datetime import datetime
from flanker.addresslib import address
from flask.ext.restful import reqparse
from sqlalchemy.orm.exc import NoResultFound
from inbox.models import Account, Calendar, Tag, Thread, Block, Message
from inbox.models.when import parse_as_when
from inbox.api.err import InputError, NotFoundError, ConflictError

MAX_LIMIT = 1000


class ValidatableArgument(reqparse.Argument):
    def handle_validation_error(self, error):
        raise InputError(str(error))


# Custom parameter types

def bounded_str(value, key):
    if len(value) > 255:
        raise ValueError('Value {} for {} is too long'.format(value, key))
    return value


def view(value, key):
    allowed_views = ["count", "ids"]
    if value not in allowed_views:
        raise ValueError('Unknown view type {}.'.format(value))
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
        raise InputError('Invalid id: {}'.format(value))
    return value


def timestamp(value, key):
    try:
        return datetime.utcfromtimestamp(int(value))
    except ValueError:
        raise ValueError('Invalid timestamp value {} for {}'.
                         format(value, key))


def strict_parse_args(parser, raw_args):
    """
    Wrapper around parser.parse_args that raises a ValueError if unexpected
    arguments are present.

    """
    args = parser.parse_args()
    unexpected_params = (set(raw_args) - {allowed_arg.name for allowed_arg in
                                          parser.args})
    if unexpected_params:
        raise InputError('Unexpected query parameters {}'.format(
                         unexpected_params))
    return args


def get_draft(draft_public_id, version, namespace_id, db_session):
    valid_public_id(draft_public_id)
    if version is None:
        raise InputError('Must specify draft version')
    try:
        draft = db_session.query(Message).filter(
            Message.public_id == draft_public_id,
            Message.namespace_id == namespace_id).one()
    except NoResultFound:
        raise NotFoundError("Couldn't find draft {}".format(draft_public_id))

    if draft.is_sent or not draft.is_draft:
        raise InputError('Message {} is not a draft'.format(draft_public_id))
    if draft.version != version:
        raise ConflictError(
            'Draft {0}.{1} has already been updated to version {2}'.
            format(draft_public_id, version, draft.version))
    return draft


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


def get_attachments(block_public_ids, namespace_id, db_session):
    attachments = set()
    if block_public_ids is None:
        return attachments
    if not isinstance(block_public_ids, list):
        raise InputError('{} is not a list of block ids'.
                         format(block_public_ids))
    for block_public_id in block_public_ids:
        # Validate public ids before querying with them
        valid_public_id(block_public_id)
        try:
            block = db_session.query(Block). \
                filter(Block.public_id == block_public_id,
                       Block.namespace_id == namespace_id).one()
            # In the future we may consider discovering the filetype from the
            # data by using #magic.from_buffer(data, mime=True))
            attachments.add(block)
        except NoResultFound:
            raise InputError('Invalid block public id {}'.
                             format(block_public_id))
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


def get_recipients(recipients, field, validate_emails=False):
    if recipients is None:
        return None
    if not isinstance(recipients, list):
        raise InputError('Invalid {} field'.format(field))
    for r in recipients:
        if not (isinstance(r, dict) and 'email' in r and
                isinstance(r['email'], basestring)):
            raise InputError('Invalid {} field'.format(field))
        if 'name' in r and not isinstance(r['name'], basestring):
            raise InputError('Invalid {} field'.format(field))
        if validate_emails:
            # flanker purports to have a more comprehensive validate_address
            # function, but it doesn't actually work. So just invoke the
            # parser.
            parsed = address.parse(r['email'], addr_spec_only=True)
            if not isinstance(parsed, address.EmailAddress):
                raise InputError(u'Invalid recipient address {}'.
                                 format(r['email']))

    return [(r.get('name', ''), r.get('email', '')) for r in recipients]


def get_calendar(calendar_public_id, namespace, db_session):
    if calendar_public_id is None:
        account = db_session.query(Account).filter(
            Account.id == namespace.account_id).one()
        return account.default_calendar
    valid_public_id(calendar_public_id)
    try:
        return db_session.query(Calendar). \
            filter(Calendar.public_id == calendar_public_id,
                   Calendar.namespace_id == namespace.id).one()
    except NoResultFound:
        raise NotFoundError('Calendar {} not found'.format(calendar_public_id))


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
            raise InputError("'participants' must have email")
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


def valid_delta_object_types(types_arg):
    types = [item.strip() for item in types_arg.split(',')]
    allowed_types = ('contact', 'message', 'event', 'file', 'message', 'tag',
                     'thread')
    for type_ in types:
        if type_ not in allowed_types:
            raise InputError('Invalid object type {}'.format(type_))
    return types


def validate_draft_recipients(draft):
    """Check that all recipient emails are at least plausible email
    addresses, before we try to send a draft."""
    for field in draft.to_addr, draft.bcc_addr, draft.cc_addr:
        if field is not None:
            for _, email_address in field:
                parsed = address.parse(email_address, addr_spec_only=True)
                if not isinstance(parsed, address.EmailAddress):
                    raise InputError(u'Invalid recipient address {}'.
                                     format(email_address))


# TODO[k]
def validate_search_query(query):
    if query is None:
        return

    return
