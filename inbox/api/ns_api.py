import os
import base64
import email.header
import uuid
import gevent
import time
from datetime import datetime

from flask import request, g, Blueprint, make_response, Response
from flask import jsonify as flask_jsonify
from flask.ext.restful import reqparse
from sqlalchemy import asc, func
from sqlalchemy.orm.exc import NoResultFound

from inbox.models import (Message, Block, Part, Thread, Namespace,
                          Contact, Calendar, Event, Transaction,
                          DataProcessingCache, Category, MessageCategory)
from inbox.models.event import RecurringEvent, RecurringEventOverride
from inbox.api.sending import send_draft, send_raw_mime
from inbox.api.update import update_message, update_thread
from inbox.api.kellogs import APIEncoder
from inbox.api import filtering
from inbox.api.validation import (get_attachments, get_calendar,
                                  get_recipients, get_draft, valid_public_id,
                                  valid_event, valid_event_update, timestamp,
                                  bounded_str, view, strict_parse_args,
                                  limit, offset, ValidatableArgument,
                                  strict_bool, validate_draft_recipients,
                                  validate_search_query, validate_search_sort,
                                  valid_delta_object_types, valid_display_name,
                                  noop_event_update)
from inbox.config import config
from inbox.contacts.algorithms import (calculate_contact_scores,
                                       calculate_group_scores,
                                       calculate_group_counts, is_stale)
import inbox.contacts.crud
from inbox.sendmail.base import (create_draft, update_draft, delete_draft,
                                 create_draft_from_mime, SendMailException)
from inbox.log import get_logger
from inbox.models.action_log import schedule_action
from inbox.models.session import InboxSession, session_scope
from inbox.search.base import get_search_client
from inbox.search.adaptor import NamespaceSearchEngine, SearchEngineError
from inbox.transactions import delta_sync
from inbox.api.err import err, APIException, NotFoundError, InputError
from inbox.events.ical import (generate_icalendar_invite, send_invite,
                               generate_rsvp, send_rsvp)


from inbox.ignition import main_engine
engine = main_engine()
log = get_logger()

DEFAULT_LIMIT = 100
MAX_LIMIT = 1000
LONG_POLL_REQUEST_TIMEOUT = 120

app = Blueprint(
    'namespace_api',
    __name__,
    url_prefix='/n/<namespace_public_id>')

# Configure mimetype -> extension map
# TODO perhaps expand to encompass non-standard mimetypes too
# see python mimetypes library
common_extensions = {}
mt_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'mime_types.txt')
with open(mt_path, 'r') as f:
    for x in f:
        x = x.strip()
        if not x or x.startswith('#'):
            continue
        m = x.split()
        mime_type, extensions = m[0], m[1:]
        assert extensions, 'Must have at least one extension per mimetype'
        common_extensions[mime_type.lower()] = extensions[0]


if config.get('DEBUG_PROFILING_ON'):
    from inbox.util.debug import attach_profiler
    attach_profiler()


@app.url_value_preprocessor
def pull_lang_code(endpoint, values):
    g.namespace_public_id = values.pop('namespace_public_id')


@app.before_request
def start():
    g.db_session = InboxSession(engine)
    try:
        valid_public_id(g.namespace_public_id)
        g.namespace = Namespace.from_public_id(g.namespace_public_id,
                                               g.db_session)

        g.encoder = APIEncoder(g.namespace.public_id)
    except NoResultFound:
        raise NotFoundError("Couldn't find namespace  `{0}` ".format(
            g.namespace_public_id))

    g.log = log.new(endpoint=request.endpoint,
                    account_id=g.namespace.account_id)

    g.parser = reqparse.RequestParser(argument_class=ValidatableArgument)
    g.parser.add_argument('limit', default=DEFAULT_LIMIT, type=limit,
                          location='args')
    g.parser.add_argument('offset', default=0, type=offset, location='args')


@app.after_request
def finish(response):
    if response.status_code == 200:
        g.db_session.commit()
    g.db_session.close()
    return response


@app.errorhandler(NotImplementedError)
def handle_not_implemented_error(error):
    response = flask_jsonify(message="API endpoint not yet implemented.",
                             type='api_error')
    response.status_code = 501
    return response


@app.errorhandler(APIException)
def handle_input_error(error):
    response = flask_jsonify(message=error.message,
                             type='invalid_request_error')
    response.status_code = error.status_code
    return response


#
# General namespace info
#
@app.route('/')
def index():
    return g.encoder.jsonify(g.namespace)


#
# Threads
#
@app.route('/threads/')
def thread_query_api():
    g.parser.add_argument('subject', type=bounded_str, location='args')
    g.parser.add_argument('to', type=bounded_str, location='args')
    g.parser.add_argument('from', type=bounded_str, location='args')
    g.parser.add_argument('cc', type=bounded_str, location='args')
    g.parser.add_argument('bcc', type=bounded_str, location='args')
    g.parser.add_argument('any_email', type=bounded_str, location='args')
    g.parser.add_argument('started_before', type=timestamp, location='args')
    g.parser.add_argument('started_after', type=timestamp, location='args')
    g.parser.add_argument('last_message_before', type=timestamp,
                          location='args')
    g.parser.add_argument('last_message_after', type=timestamp,
                          location='args')
    g.parser.add_argument('filename', type=bounded_str, location='args')
    g.parser.add_argument('in', type=bounded_str, location='args')
    g.parser.add_argument('thread_id', type=valid_public_id, location='args')
    g.parser.add_argument('unread', type=strict_bool, location='args')
    g.parser.add_argument('starred', type=strict_bool, location='args')
    g.parser.add_argument('view', type=view, location='args')

    # For backwards-compatibility -- remove after deprecating tags API.
    g.parser.add_argument('tag', type=bounded_str, location='args')

    args = strict_parse_args(g.parser, request.args)

    # For backwards-compatibility -- remove after deprecating tags API.
    if args['tag'] == 'unread':
        unread = True
        in_ = None
    else:
        in_ = args['in'] or args['tag']
        unread = args['unread']

    threads = filtering.threads(
        namespace_id=g.namespace.id,
        subject=args['subject'],
        thread_public_id=args['thread_id'],
        to_addr=args['to'],
        from_addr=args['from'],
        cc_addr=args['cc'],
        bcc_addr=args['bcc'],
        any_email=args['any_email'],
        started_before=args['started_before'],
        started_after=args['started_after'],
        last_message_before=args['last_message_before'],
        last_message_after=args['last_message_after'],
        filename=args['filename'],
        unread=unread,
        starred=args['starred'],
        in_=in_,
        limit=args['limit'],
        offset=args['offset'],
        view=args['view'],
        db_session=g.db_session)

    # Use a new encoder object with the expand parameter set.
    encoder = APIEncoder(g.namespace.public_id, args['view'] == 'expanded')
    return encoder.jsonify(threads)


@app.route('/threads/search', methods=['GET', 'POST'])
def thread_search_api():
    g.parser.add_argument('q', type=bounded_str, location='args')
    args = strict_parse_args(g.parser, request.args)
    if request.method == 'GET':
        if not args['q']:
            err_string = ('GET HTTP method must include query'
                          ' url parameter')
            g.log.error(err_string)
            return err(400, err_string)

        search_client = get_search_client(g.namespace.account)
        results = search_client.search_threads(g.db_session, args['q'])
    else:
        data = request.get_json(force=True)

        query = data.get('query')
        validate_search_query(query)

        sort = data.get('sort')
        validate_search_sort(sort)

        try:
            search_engine = NamespaceSearchEngine(g.namespace_public_id)
            results = search_engine.threads.search(query=query,
                                                   sort=sort,
                                                   max_results=args.limit,
                                                   offset=args.offset)
        except SearchEngineError as e:
            g.log.error('Search error: {0}'.format(e))
            return err(501, 'Search error')

    return g.encoder.jsonify(results)


@app.route('/threads/<public_id>')
def thread_api(public_id):
    g.parser.add_argument('view', type=view, location='args')
    args = strict_parse_args(g.parser, request.args)
    # Use a new encoder object with the expand parameter set.
    encoder = APIEncoder(g.namespace.public_id, args['view'] == 'expanded')
    try:
        valid_public_id(public_id)
        thread = g.db_session.query(Thread).filter(
            Thread.public_id == public_id,
            Thread.namespace_id == g.namespace.id).one()
        return encoder.jsonify(thread)
    except NoResultFound:
        raise NotFoundError("Couldn't find thread `{0}`".format(public_id))


#
# Update thread
#
@app.route('/threads/<public_id>', methods=['PUT'])
def thread_api_update(public_id):
    try:
        valid_public_id(public_id)
        thread = g.db_session.query(Thread).filter(
            Thread.public_id == public_id,
            Thread.namespace_id == g.namespace.id).one()
    except NoResultFound:
        raise NotFoundError("Couldn't find thread `{0}` ".format(public_id))
    data = request.get_json(force=True)
    if not isinstance(data, dict):
        raise InputError('Invalid request body')
    update_thread(thread, data, g.db_session)
    return g.encoder.jsonify(thread)


#
#  Delete thread
#
@app.route('/threads/<public_id>', methods=['DELETE'])
def thread_api_delete(public_id):
    """ Moves the thread to the trash """
    raise NotImplementedError


##
# Messages
##
@app.route('/messages/')
def message_query_api():
    g.parser.add_argument('subject', type=bounded_str, location='args')
    g.parser.add_argument('to', type=bounded_str, location='args')
    g.parser.add_argument('from', type=bounded_str, location='args')
    g.parser.add_argument('cc', type=bounded_str, location='args')
    g.parser.add_argument('bcc', type=bounded_str, location='args')
    g.parser.add_argument('any_email', type=bounded_str, location='args')
    g.parser.add_argument('started_before', type=timestamp, location='args')
    g.parser.add_argument('started_after', type=timestamp, location='args')
    g.parser.add_argument('last_message_before', type=timestamp,
                          location='args')
    g.parser.add_argument('last_message_after', type=timestamp,
                          location='args')
    g.parser.add_argument('filename', type=bounded_str, location='args')
    g.parser.add_argument('in', type=bounded_str, location='args')
    g.parser.add_argument('thread_id', type=valid_public_id, location='args')
    g.parser.add_argument('unread', type=strict_bool, location='args')
    g.parser.add_argument('starred', type=strict_bool, location='args')
    g.parser.add_argument('view', type=view, location='args')

    # For backwards-compatibility -- remove after deprecating tags API.
    g.parser.add_argument('tag', type=bounded_str, location='args')
    args = strict_parse_args(g.parser, request.args)

    # For backwards-compatibility -- remove after deprecating tags API.
    in_ = args['in'] or args['tag']

    messages = filtering.messages_or_drafts(
        namespace_id=g.namespace.id,
        drafts=False,
        subject=args['subject'],
        thread_public_id=args['thread_id'],
        to_addr=args['to'],
        from_addr=args['from'],
        cc_addr=args['cc'],
        bcc_addr=args['bcc'],
        any_email=args['any_email'],
        started_before=args['started_before'],
        started_after=args['started_after'],
        last_message_before=args['last_message_before'],
        last_message_after=args['last_message_after'],
        filename=args['filename'],
        in_=in_,
        unread=args['unread'],
        starred=args['starred'],
        limit=args['limit'],
        offset=args['offset'],
        view=args['view'],
        db_session=g.db_session)

    # Use a new encoder object with the expand parameter set.
    encoder = APIEncoder(g.namespace.public_id, args['view'] == 'expanded')
    return encoder.jsonify(messages)


@app.route('/messages/search', methods=['GET', 'POST'])
def message_search_api():
    g.parser.add_argument('q', type=bounded_str, location='args')
    args = strict_parse_args(g.parser, request.args)
    if request.method == 'GET':
        if not args['q']:
            err_string = ('GET HTTP method must include query'
                          ' url parameter')
            g.log.error(err_string)
            return err(400, err_string)

        search_client = get_search_client(g.namespace.account)
        results = search_client.search_messages(g.db_session, args['q'])
    else:
        data = request.get_json(force=True)
        query = data.get('query')

        validate_search_query(query)

        sort = data.get('sort')
        validate_search_sort(sort)
        try:
            search_engine = NamespaceSearchEngine(g.namespace_public_id)
            results = search_engine.messages.search(query=query,
                                                    sort=sort,
                                                    max_results=args.limit,
                                                    offset=args.offset)
        except SearchEngineError as e:
            g.log.error('Search error: {0}'.format(e))
            return err(501, 'Search error')

    return g.encoder.jsonify(results)


@app.route('/messages/<public_id>', methods=['GET'])
def message_read_api(public_id):
    g.parser.add_argument('view', type=view, location='args')
    args = strict_parse_args(g.parser, request.args)
    encoder = APIEncoder(g.namespace.public_id, args['view'] == 'expanded')

    try:
        valid_public_id(public_id)
        message = Message.from_public_id(public_id, g.namespace.id,
                                         g.db_session)
    except NoResultFound:
        raise NotFoundError("Couldn't find message {0} ".format(public_id))

    if request.headers.get('Accept', None) == 'message/rfc822':
        if message.full_body is not None:
            return Response(message.full_body.data,
                            mimetype='message/rfc822')
        else:
            g.log.error("Message without full_body attribute: id='{0}'"
                        .format(message.id))
            raise NotFoundError(
                "Couldn't find raw contents for message `{0}` "
                .format(public_id))

    return encoder.jsonify(message)


@app.route('/messages/<public_id>', methods=['PUT'])
def message_update_api(public_id):
    try:
        valid_public_id(public_id)
        message = g.db_session.query(Message).filter(
            Message.public_id == public_id,
            Message.namespace_id == g.namespace.id).one()
    except NoResultFound:
        raise NotFoundError("Couldn't find message {0} ".format(public_id))
    data = request.get_json(force=True)
    if not isinstance(data, dict):
        raise InputError('Invalid request body')
    update_message(message, data, g.db_session)
    return g.encoder.jsonify(message)


# TODO Deprecate this endpoint once API usage falls off
@app.route('/messages/<public_id>/rfc2822', methods=['GET'])
def raw_message_api(public_id):
    try:
        valid_public_id(public_id)
        message = g.db_session.query(Message).filter(
            Message.public_id == public_id,
            Message.namespace_id == g.namespace.id).one()
    except NoResultFound:
        raise NotFoundError("Couldn't find message {0}".format(public_id))

    if message.full_body is None:
        raise NotFoundError("Couldn't find message {0}".format(public_id))

    if message.full_body is not None:
        b64_contents = base64.b64encode(message.full_body.data)
    else:
        g.log.error("Message without full_body attribute: id='{0}'"
                    .format(message.id))
        raise NotFoundError(
                    "Couldn't find raw contents for message `{0}` "
                    .format(public_id))
    return g.encoder.jsonify({"rfc2822": b64_contents})


# Folders / Labels
@app.route('/folders')
@app.route('/labels')
def folders_labels_query_api():
    g.parser.add_argument('view', type=bounded_str, location='args')
    args = strict_parse_args(g.parser, request.args)
    if args['view'] == 'count':
        results = g.db_session.query(func.count(Category.id))
    elif args['view'] == 'ids':
        results = g.db_session.query(Category.public_id)
    else:
        results = g.db_session.query(Category)

    results = results.filter(Category.namespace_id == g.namespace.id)
    results = results.order_by(asc(Category.id))

    if args['view'] == 'count':
        return g.encoder.jsonify({"count": results.scalar()})

    results = results.limit(args['limit']).offset(args['offset']).all()
    if args['view'] == 'ids':
        return g.encoder.jsonify([r for r, in results])
    return g.encoder.jsonify(results)


@app.route('/folders/<public_id>')
def folder_api(public_id):
    return folders_labels_api_impl(public_id)


@app.route('/labels/<public_id>')
def label_api(public_id):
    return folders_labels_api_impl(public_id)


def folders_labels_api_impl(public_id):
    valid_public_id(public_id)
    try:
        category = g.db_session.query(Category).filter(
            Category.namespace_id == g.namespace.id,
            Category.public_id == public_id).first()
    except NoResultFound:
        raise NotFoundError('Object not found')
    return g.encoder.jsonify(category)


@app.route('/folders', methods=['POST'])
@app.route('/labels', methods=['POST'])
def folders_labels_create_api():
    category_type = g.namespace.account.category_type
    data = request.get_json(force=True)
    display_name = data.get('display_name')

    valid_display_name(g.namespace.id, category_type, display_name,
                       g.db_session)

    category = Category.find_or_create(g.db_session, g.namespace.id,
                                       name=None, display_name=display_name,
                                       type_=category_type)
    g.db_session.flush()

    if category_type == 'folder':
        schedule_action('create_folder', category, g.namespace.id,
                        g.db_session)
    else:
        schedule_action('create_label', category, g.namespace.id, g.db_session)

    return g.encoder.jsonify(category)


@app.route('/folders/<public_id>', methods=['PUT'])
@app.route('/labels/<public_id>', methods=['PUT'])
def folder_label_update_api(public_id):
    category_type = g.namespace.account.category_type
    valid_public_id(public_id)
    try:
        category = g.db_session.query(Category).filter(
            Category.namespace_id == g.namespace.id,
            Category.public_id == public_id).one()
    except NoResultFound:
        raise InputError("Couldn't find {} {}".format(
            category_type, public_id))
    if category.name is not None:
        raise InputError("Cannot modify a standard {}".format(category_type))

    data = request.get_json(force=True)
    display_name = data.get('display_name')
    valid_display_name(g.namespace.id, category_type, display_name,
                       g.db_session)

    current_name = category.display_name
    category.display_name = display_name
    g.db_session.flush()

    if category_type == 'folder':
        schedule_action('update_folder', category, g.namespace.id,
                        g.db_session, old_name=current_name)
    else:
        schedule_action('update_label', category, g.namespace.id,
                        g.db_session, old_name=current_name)

    # TODO[k]: Update corresponding folder/ label once syncback is successful,
    # rather than waiting for sync to pick it up?

    return g.encoder.jsonify(category)


# -- Begin tags API shim


@app.route('/tags')
def tag_query_api():
    categories = g.db_session.query(Category). \
        filter(Category.namespace_id == g.namespace.id)
    resp = [
        {'object': 'tag',
         'name': obj.display_name,
         'id': obj.name or obj.public_id,
         'namespace_id': g.namespace.public_id,
         'readonly': False} for obj in categories
    ]
    return g.encoder.jsonify(resp)


@app.route('/tags/<public_id>')
def tag_detail_api(public_id):
    # Interpret former special public ids for 'canonical' tags.
    if public_id in ('inbox', 'sent', 'archive', 'important', 'trash', 'spam',
                     'all'):
        category = g.db_session.query(Category). \
            filter(Category.namespace_id == g.namespace.id,
                   Category.name == public_id).first()
    else:
        category = g.db_session.query(Category). \
            filter(Category.namespace_id == g.namespace.id,
                   Category.public_id == public_id).first()
    if category is None:
        raise NotFoundError('Category {} not found'.format(public_id))

    message_subquery = g.db_session.query(Message.thread_id). \
        join(MessageCategory). \
        filter(
            Message.namespace_id == g.namespace.id,
            MessageCategory.category_id == category.id).subquery()
    thread_count = g.db_session.query(func.count(1)). \
        select_from(Thread).filter(
            Thread.id.in_(message_subquery)).scalar()

    unread_subquery = g.db_session.query(Message.thread_id). \
        join(MessageCategory). \
        filter(
            Message.namespace_id == g.namespace.id,
            MessageCategory.category_id == category.id,
            Message.is_read == False).subquery()
    unread_count = g.db_session.query(func.count(1)). \
        select_from(Thread).filter(
            Thread.id.in_(unread_subquery)).scalar()

    return g.encoder.jsonify({
        'object': 'tag',
        'name': category.display_name,
        'id': category.name or category.public_id,
        'namespace_id': g.namespace.public_id,
        'readonly': False,
        'unread_count': unread_count,
        'thread_count': thread_count
    })


# -- End tags API shim


#
# Contacts
##
@app.route('/contacts/', methods=['GET'])
def contact_api():
    g.parser.add_argument('filter', type=bounded_str, default='',
                          location='args')
    g.parser.add_argument('view', type=bounded_str, location='args')

    args = strict_parse_args(g.parser, request.args)
    if args['view'] == 'count':
        results = g.db_session.query(func.count(Contact.id))
    elif args['view'] == 'ids':
        results = g.db_session.query(Contact.public_id)
    else:
        results = g.db_session.query(Contact)

    results = results.filter(Contact.namespace_id == g.namespace.id)

    if args['filter']:
        results = results.filter(Contact.email_address == args['filter'])
    results = results.order_by(asc(Contact.id))

    if args['view'] == 'count':
        return g.encoder.jsonify({"count": results.scalar()})

    results = results.limit(args['limit']).offset(args['offset']).all()
    if args['view'] == 'ids':
        return g.encoder.jsonify([r for r, in results])

    return g.encoder.jsonify(results)


@app.route('/contacts/<public_id>', methods=['GET'])
def contact_read_api(public_id):
    # Get all data for an existing contact.
    valid_public_id(public_id)
    result = inbox.contacts.crud.read(g.namespace, g.db_session, public_id)
    if result is None:
        raise NotFoundError("Couldn't find contact {0}".format(public_id))
    return g.encoder.jsonify(result)


##
# Events
##
@app.route('/events/', methods=['GET'])
def event_api():
    g.parser.add_argument('event_id', type=valid_public_id, location='args')
    g.parser.add_argument('calendar_id', type=valid_public_id, location='args')
    g.parser.add_argument('title', type=bounded_str, location='args')
    g.parser.add_argument('description', type=bounded_str, location='args')
    g.parser.add_argument('location', type=bounded_str, location='args')
    g.parser.add_argument('busy', type=strict_bool, location='args')
    g.parser.add_argument('starts_before', type=timestamp, location='args')
    g.parser.add_argument('starts_after', type=timestamp, location='args')
    g.parser.add_argument('ends_before', type=timestamp, location='args')
    g.parser.add_argument('ends_after', type=timestamp, location='args')
    g.parser.add_argument('view', type=bounded_str, location='args')
    g.parser.add_argument('expand_recurring', type=strict_bool,
                          location='args')
    g.parser.add_argument('show_cancelled', type=strict_bool, location='args')

    args = strict_parse_args(g.parser, request.args)

    results = filtering.events(
        namespace_id=g.namespace.id,
        event_public_id=args['event_id'],
        calendar_public_id=args['calendar_id'],
        title=args['title'],
        description=args['description'],
        location=args['location'],
        busy=args['busy'],
        starts_before=args['starts_before'],
        starts_after=args['starts_after'],
        ends_before=args['ends_before'],
        ends_after=args['ends_after'],
        limit=args['limit'],
        offset=args['offset'],
        view=args['view'],
        expand_recurring=args['expand_recurring'],
        show_cancelled=args['show_cancelled'],
        db_session=g.db_session)

    return g.encoder.jsonify(results)


@app.route('/events/', methods=['POST'])
def event_create_api():
    g.parser.add_argument('notify_participants', type=strict_bool,
                          location='args')
    args = strict_parse_args(g.parser, request.args)
    notify_participants = args['notify_participants']

    data = request.get_json(force=True)
    calendar = get_calendar(data.get('calendar_id'),
                            g.namespace, g.db_session)

    if calendar.read_only:
        raise InputError("Can't create events on read_only calendar.")

    valid_event(data)

    title = data.get('title', '')
    description = data.get('description')
    location = data.get('location')
    when = data.get('when')
    busy = data.get('busy')
    # client libraries can send explicit key = None automagically
    if busy is None:
        busy = True

    participants = data.get('participants')
    if participants is None:
        participants = []

    for p in participants:
        if 'status' not in p:
            p['status'] = 'noreply'

    event = Event(
        calendar=calendar,
        namespace=g.namespace,
        uid=uuid.uuid4().hex,
        provider_name=g.namespace.account.provider,
        raw_data='',
        title=title,
        description=description,
        location=location,
        busy=busy,
        when=when,
        read_only=False,
        is_owner=True,
        participants=participants,
        sequence_number=0,
        source='local')
    g.db_session.add(event)
    g.db_session.flush()

    schedule_action('create_event', event, g.namespace.id, g.db_session,
                    calendar_uid=event.calendar.uid,
                    notify_participants=notify_participants)
    return g.encoder.jsonify(event)


@app.route('/events/<public_id>', methods=['GET'])
def event_read_api(public_id):
    """Get all data for an existing event."""
    valid_public_id(public_id)
    try:
        event = g.db_session.query(Event).filter(
            Event.namespace_id == g.namespace.id,
            Event.public_id == public_id).one()
    except NoResultFound:
        raise NotFoundError("Couldn't find event id {0}".format(public_id))
    return g.encoder.jsonify(event)


@app.route('/events/<public_id>', methods=['PUT'])
def event_update_api(public_id):
    g.parser.add_argument('notify_participants', type=strict_bool,
                          location='args')
    args = strict_parse_args(g.parser, request.args)
    notify_participants = args['notify_participants']

    valid_public_id(public_id)
    try:
        event = g.db_session.query(Event).filter(
            Event.public_id == public_id,
            Event.namespace_id == g.namespace.id).one()
    except NoResultFound:
        raise NotFoundError("Couldn't find event {0}".format(public_id))
    if event.read_only:
        raise InputError('Cannot update read_only event.')
    if (isinstance(event, RecurringEvent) or
            isinstance(event, RecurringEventOverride)):
        raise InputError('Cannot update a recurring event yet.')

    data = request.get_json(force=True)
    account = g.namespace.account

    valid_event_update(data, g.namespace, g.db_session)

    if 'participants' in data:
        for p in data['participants']:
            if 'status' not in p:
                p['status'] = 'noreply'

    # Don't update an event if we don't need to.
    if noop_event_update(event, data):
        return g.encoder.jsonify(event)

    for attr in ['title', 'description', 'location', 'when', 'participants']:
        if attr in data:
            setattr(event, attr, data[attr])

    event.sequence_number += 1
    g.db_session.commit()

    # Don't sync back updates to autoimported events.
    if event.calendar != account.emailed_events_calendar:
        schedule_action('update_event', event, g.namespace.id, g.db_session,
                        calendar_uid=event.calendar.uid,
                        notify_participants=notify_participants)

    return g.encoder.jsonify(event)


@app.route('/events/<public_id>', methods=['DELETE'])
def event_delete_api(public_id):
    g.parser.add_argument('notify_participants', type=strict_bool,
                          location='args')
    args = strict_parse_args(g.parser, request.args)
    notify_participants = args['notify_participants']

    valid_public_id(public_id)
    try:
        event = g.db_session.query(Event).filter_by(
            public_id=public_id,
            namespace_id=g.namespace.id).one()
    except NoResultFound:
        raise NotFoundError("Couldn't find event {0}".format(public_id))
    if event.calendar.read_only:
        raise InputError('Cannot delete event {} from read_only calendar.'.
                         format(public_id))

    # Set the local event status to 'cancelled' rather than deleting it,
    # in order to be consistent with how we sync deleted events from the
    # remote, and consequently return them through the events, delta sync APIs
    event.sequence_number += 1
    event.status = 'cancelled'
    g.db_session.commit()

    account = g.namespace.account

    # FIXME @karim: do this in the syncback thread instead.
    if notify_participants and account.provider != 'gmail':
        ical_file = generate_icalendar_invite(event,
                                              invite_type='cancel').to_ical()

        send_invite(ical_file, event, account, invite_type='cancel')

    schedule_action('delete_event', event, g.namespace.id, g.db_session,
                    event_uid=event.uid, calendar_name=event.calendar.name,
                    calendar_uid=event.calendar.uid,
                    notify_participants=notify_participants)

    return g.encoder.jsonify(None)


@app.route('/send-rsvp', methods=['POST'])
def event_rsvp_api():
    data = request.get_json(force=True)

    event_id = data.get('event_id')
    valid_public_id(event_id)
    try:
        event = g.db_session.query(Event).filter(
            Event.public_id == event_id,
            Event.namespace_id == g.namespace.id).one()
    except NoResultFound:
        raise NotFoundError("Couldn't find event {0}".format(event_id))

    if event.message is None:
        raise InputError('This is not a message imported '
                         'from an iCalendar invite.')

    status = data.get('status')
    if not status:
        raise InputError('You must define a status to RSVP.')

    if status not in ['yes', 'no', 'maybe']:
        raise InputError('Invalid status %s' % status)

    comment = data.get('comment', '')

    # Note: this assumes that the email invite was directly addressed to us
    # (i.e: that there's no email alias to redirect ben.bitdiddle@nylas
    #  to ben@nylas.)
    participants = {p["email"]: p for p in event.participants}

    account = g.namespace.account
    email = account.email_address

    if email not in participants:
        raise InputError('Cannot find %s among the participants' % email)

    participant = {"email": email, "status": status, "comment": comment}

    body_text = comment
    ical_data = generate_rsvp(event, participant, account)

    if ical_data is None:
        raise APIException("Couldn't parse the attached iCalendar invite")

    try:
        send_rsvp(ical_data, event, body_text, status, account)
    except SendMailException as exc:
        kwargs = {}
        if exc.failures:
            kwargs['failures'] = exc.failures
        if exc.server_error:
            kwargs['server_error'] = exc.server_error
        return err(exc.http_code, exc.message, **kwargs)

    # Update the participants status too.
    new_participants = []
    for participant in event.participants:
        email = participant.get("email")
        if email is not None and email == account.email_address:
            participant["status"] = status
            if comment != "":
                participant["comment"] = comment

        new_participants.append(participant)

    event.participants = []
    for participant in new_participants:
        event.participants.append(participant)

    g.db_session.commit()
    return g.encoder.jsonify(event)


#
# Files
#
@app.route('/files/', methods=['GET'])
def files_api():
    g.parser.add_argument('filename', type=bounded_str, location='args')
    g.parser.add_argument('message_id', type=valid_public_id, location='args')
    g.parser.add_argument('content_type', type=bounded_str, location='args')
    g.parser.add_argument('view', type=view, location='args')

    args = strict_parse_args(g.parser, request.args)

    files = filtering.files(
        namespace_id=g.namespace.id,
        message_public_id=args['message_id'],
        filename=args['filename'],
        content_type=args['content_type'],
        limit=args['limit'],
        offset=args['offset'],
        view=args['view'],
        db_session=g.db_session)

    return g.encoder.jsonify(files)


@app.route('/files/<public_id>', methods=['GET'])
def file_read_api(public_id):
    valid_public_id(public_id)
    try:
        f = g.db_session.query(Block).filter(
            Block.public_id == public_id,
            Block.namespace_id == g.namespace.id).one()
        return g.encoder.jsonify(f)
    except NoResultFound:
        raise NotFoundError("Couldn't find file {0} ".format(public_id))


@app.route('/files/<public_id>', methods=['DELETE'])
def file_delete_api(public_id):
    valid_public_id(public_id)
    try:
        f = g.db_session.query(Block).filter(
            Block.public_id == public_id,
            Block.namespace_id == g.namespace.id).one()

        if g.db_session.query(Block).join(Part) \
                .filter(Block.public_id == public_id).first() is not None:
            raise InputError("Can't delete file that is attachment.")

        g.db_session.delete(f)
        g.db_session.commit()

        # This is essentially what our other API endpoints do after deleting.
        # Effectively no error == success
        return g.encoder.jsonify(None)
    except NoResultFound:
        raise NotFoundError("Couldn't find file {0} ".format(public_id))


#
# Upload file API. This actually supports multiple files at once
# You can test with
# $ curl http://localhost:5555/n/4s4iz36h36w17kumggi36ha2b/files \
# --form upload=@dancingbaby.gif
@app.route('/files/', methods=['POST'])
def file_upload_api():
    all_files = []
    for name, uploaded in request.files.iteritems():
        g.log.info("Processing upload '{0}'".format(name))
        f = Block()
        f.namespace = g.namespace
        f.content_type = uploaded.content_type
        f.filename = uploaded.filename
        f.data = uploaded.read()
        all_files.append(f)

    g.db_session.add_all(all_files)
    g.db_session.commit()  # to generate public_ids

    return g.encoder.jsonify(all_files)


#
# File downloads
#
@app.route('/files/<public_id>/download')
def file_download_api(public_id):
    valid_public_id(public_id)
    try:
        f = g.db_session.query(Block).filter(
            Block.public_id == public_id,
            Block.namespace_id == g.namespace.id).one()
    except NoResultFound:
        raise NotFoundError("Couldn't find file {0} ".format(public_id))

    # Here we figure out the filename.extension given the
    # properties which were set on the original attachment
    # TODO consider using werkzeug.secure_filename to sanitize?

    if f.content_type:
        ct = f.content_type.lower()
    else:
        # TODO Detect the content-type using the magic library
        # and set ct = the content type, which is used below
        g.log.error("Content type not set! Defaulting to text/plain")
        ct = 'text/plain'

    if f.filename:
        name = f.filename
    else:
        g.log.debug("No filename. Generating...")
        if ct in common_extensions:
            name = 'attachment.{0}'.format(common_extensions[ct])
        else:
            g.log.error("Unknown extension for content-type: {0}"
                        .format(ct))
            # HACK just append the major part of the content type
            name = 'attachment.{0}'.format(ct.split('/')[0])

    # TODO the part.data object should really behave like a stream we can read
    # & write to
    response = make_response(f.data)

    response.headers['Content-Type'] = 'application/octet-stream'  # ct
    # Werkzeug will try to encode non-ascii header values as latin-1. Try that
    # first; if it fails, use RFC2047/MIME encoding. See
    # https://tools.ietf.org/html/rfc7230#section-3.2.4.
    try:
        name = name.encode('latin-1')
    except UnicodeEncodeError:
        name = email.header.Header(name, 'utf-8').encode()
    response.headers['Content-Disposition'] = \
        'attachment; filename={0}'.format(name)
    g.log.info(response.headers)
    return response


##
# Calendars
##
@app.route('/calendars/', methods=['GET'])
def calendar_api():
    g.parser.add_argument('view', type=view, location='args')

    args = strict_parse_args(g.parser, request.args)
    if args['view'] == 'count':
        query = g.db_session.query(func.count(Calendar.id))
    elif args['view'] == 'ids':
        query = g.db_session.query(Calendar.public_id)
    else:
        query = g.db_session.query(Calendar)

    results = query.filter(Calendar.namespace_id == g.namespace.id). \
        order_by(asc(Calendar.id))

    if args['view'] == 'count':
        return g.encoder.jsonify({"count": results.scalar()})

    results = results.limit(args['limit']).offset(args['offset']).all()
    if args['view'] == 'ids':
        return g.encoder.jsonify([r for r, in results])

    return g.encoder.jsonify(results)


@app.route('/calendars/<public_id>', methods=['GET'])
def calendar_read_api(public_id):
    """Get all data for an existing calendar."""
    valid_public_id(public_id)

    try:
        calendar = g.db_session.query(Calendar).filter(
            Calendar.public_id == public_id,
            Calendar.namespace_id == g.namespace.id).one()
    except NoResultFound:
        raise NotFoundError("Couldn't find calendar {0}".format(public_id))
    return g.encoder.jsonify(calendar)


##
# Drafts
##

# TODO(emfree, kavya): Systematically validate user input, and return
# meaningful errors for invalid input.

@app.route('/drafts/', methods=['GET'])
def draft_query_api():
    g.parser.add_argument('subject', type=bounded_str, location='args')
    g.parser.add_argument('to', type=bounded_str, location='args')
    g.parser.add_argument('cc', type=bounded_str, location='args')
    g.parser.add_argument('bcc', type=bounded_str, location='args')
    g.parser.add_argument('any_email', type=bounded_str, location='args')
    g.parser.add_argument('started_before', type=timestamp, location='args')
    g.parser.add_argument('started_after', type=timestamp, location='args')
    g.parser.add_argument('last_message_before', type=timestamp,
                          location='args')
    g.parser.add_argument('last_message_after', type=timestamp,
                          location='args')
    g.parser.add_argument('filename', type=bounded_str, location='args')
    g.parser.add_argument('in', type=bounded_str, location='args')
    g.parser.add_argument('thread_id', type=valid_public_id, location='args')
    g.parser.add_argument('unread', type=strict_bool, location='args')
    g.parser.add_argument('starred', type=strict_bool, location='args')
    g.parser.add_argument('view', type=view, location='args')

    args = strict_parse_args(g.parser, request.args)

    drafts = filtering.messages_or_drafts(
        namespace_id=g.namespace.id,
        drafts=True,
        subject=args['subject'],
        thread_public_id=args['thread_id'],
        to_addr=args['to'],
        from_addr=None,
        cc_addr=args['cc'],
        bcc_addr=args['bcc'],
        any_email=args['any_email'],
        started_before=args['started_before'],
        started_after=args['started_after'],
        last_message_before=args['last_message_before'],
        last_message_after=args['last_message_after'],
        filename=args['filename'],
        in_=args['in'],
        unread=args['unread'],
        starred=args['starred'],
        limit=args['limit'],
        offset=args['offset'],
        view=args['view'],
        db_session=g.db_session)

    return g.encoder.jsonify(drafts)


@app.route('/drafts/<public_id>', methods=['GET'])
def draft_get_api(public_id):
    valid_public_id(public_id)
    draft = g.db_session.query(Message).filter(
        Message.public_id == public_id,
        Message.namespace_id == g.namespace.id).first()
    if draft is None:
        raise NotFoundError("Couldn't find draft {}".format(public_id))
    return g.encoder.jsonify(draft)


@app.route('/drafts/', methods=['POST'])
def draft_create_api():
    data = request.get_json(force=True)
    draft = create_draft(data, g.namespace, g.db_session, syncback=True)
    return g.encoder.jsonify(draft)


@app.route('/drafts/<public_id>', methods=['PUT'])
def draft_update_api(public_id):
    data = request.get_json(force=True)
    original_draft = get_draft(public_id, data.get('version'), g.namespace.id,
                               g.db_session)

    # TODO(emfree): what if you try to update a draft on a *thread* that's been
    # deleted?

    data = request.get_json(force=True)

    to = get_recipients(data.get('to'), 'to')
    cc = get_recipients(data.get('cc'), 'cc')
    bcc = get_recipients(data.get('bcc'), 'bcc')
    from_addr = get_recipients(data.get('from_addr'), 'from_addr')
    reply_to = get_recipients(data.get('reply_to'), 'reply_to')

    if from_addr and len(from_addr) > 1:
        raise InputError("from_addr field can have at most one item")
    if reply_to and len(reply_to) > 1:
        raise InputError("reply_to field can have at most one item")

    subject = data.get('subject')
    body = data.get('body')
    files = get_attachments(data.get('file_ids'), g.namespace.id, g.db_session)

    draft = update_draft(g.db_session, g.namespace.account, original_draft,
                         to, subject, body, files, cc, bcc, from_addr,
                         reply_to)
    return g.encoder.jsonify(draft)


@app.route('/drafts/<public_id>', methods=['DELETE'])
def draft_delete_api(public_id):
    data = request.get_json(force=True)
    # Validate draft id, version, etc.
    draft = get_draft(public_id, data.get('version'), g.namespace.id,
                      g.db_session)

    result = delete_draft(g.db_session, g.namespace.account, draft)
    return g.encoder.jsonify(result)


@app.route('/send', methods=['POST'])
def draft_send_api():
    if request.content_type == "message/rfc822":
        msg = create_draft_from_mime(g.namespace.account, request.data,
                                     g.db_session)
        validate_draft_recipients(msg)
        resp = send_raw_mime(g.namespace.account, g.db_session, msg)
        return resp

    data = request.get_json(force=True)
    draft_public_id = data.get('draft_id')
    if draft_public_id is not None:
        draft = get_draft(draft_public_id, data.get('version'), g.namespace.id,
                          g.db_session)
        schedule_action('delete_draft', draft, draft.namespace.id,
                        g.db_session, inbox_uid=draft.inbox_uid,
                        message_id_header=draft.message_id_header)
    else:
        draft = create_draft(data, g.namespace, g.db_session, syncback=False)

    validate_draft_recipients(draft)
    resp = send_draft(g.namespace.account, draft, g.db_session)
    return resp


##
# Client syncing
##
@app.route('/delta')
@app.route('/delta/longpoll')
def sync_deltas():
    g.parser.add_argument('cursor', type=valid_public_id, location='args',
                          required=True)
    g.parser.add_argument('exclude_types', type=valid_delta_object_types,
                          location='args')
    g.parser.add_argument('include_types', type=valid_delta_object_types,
                          location='args')
    g.parser.add_argument('timeout', type=int,
                          default=LONG_POLL_REQUEST_TIMEOUT, location='args')
    # - Begin shim -
    # Remove after folders and labels exposed in the Delta API for everybody,
    # right now, only expose for Edgehill.
    g.parser.add_argument('exclude_folders', type=strict_bool, location='args')
    # - End shim -
    # TODO(emfree): should support `expand` parameter in delta endpoints.
    args = strict_parse_args(g.parser, request.args)
    exclude_types = args.get('exclude_types')
    include_types = args.get('include_types')
    # - Begin shim -
    exclude_folders = args.get('exclude_folders')
    if exclude_folders is None:
        exclude_folders = True
    # - End shim -
    cursor = args['cursor']
    timeout = args['timeout']

    if include_types and exclude_types:
        return err(400, "Invalid Request. Cannot specify both include_types"
                   "and exclude_types")

    if cursor == '0':
        start_pointer = 0
    else:
        try:
            start_pointer, = g.db_session.query(Transaction.id). \
                filter(Transaction.public_id == cursor,
                       Transaction.namespace_id == g.namespace.id).one()
        except NoResultFound:
            raise InputError('Invalid cursor parameter')

    # The client wants us to wait until there are changes
    g.db_session.close()  # hack to close the flask session
    poll_interval = 1

    start_time = time.time()
    while time.time() - start_time < timeout:
        with session_scope() as db_session:
            deltas, _ = delta_sync.format_transactions_after_pointer(
                g.namespace, start_pointer, db_session, args['limit'],
                exclude_types, include_types, exclude_folders)

        response = {
            'cursor_start': cursor,
            'deltas': deltas,
        }
        if deltas:
            response['cursor_end'] = deltas[-1]['cursor']
            return g.encoder.jsonify(response)

        # No changes. perhaps wait
        elif '/delta/longpoll' in request.url_rule.rule:
            gevent.sleep(poll_interval)
        else:  # Return immediately
            response['cursor_end'] = cursor
            return g.encoder.jsonify(response)

    # If nothing happens until timeout, just return the end of the cursor
    response['cursor_end'] = cursor
    return g.encoder.jsonify(response)


@app.route('/delta/generate_cursor', methods=['POST'])
def generate_cursor():
    data = request.get_json(force=True)

    if data.keys() != ['start'] or not isinstance(data['start'], int):
        raise InputError('generate_cursor request body must have the format '
                         '{"start": <Unix timestamp> (seconds)}')

    timestamp = int(data['start'])

    try:
        datetime.utcfromtimestamp(timestamp)
    except ValueError:
        raise InputError('generate_cursor request body must have the format '
                         '{"start": <Unix timestamp> (seconds)}')

    cursor = delta_sync.get_transaction_cursor_near_timestamp(
        g.namespace.id, timestamp, g.db_session)
    return g.encoder.jsonify({'cursor': cursor})


##
# Streaming
##

@app.route('/delta/streaming')
def stream_changes():
    g.parser.add_argument('timeout', type=float, location='args')
    g.parser.add_argument('cursor', type=valid_public_id, location='args',
                          required=True)
    g.parser.add_argument('exclude_types', type=valid_delta_object_types,
                          location='args')
    g.parser.add_argument('include_types', type=valid_delta_object_types,
                          location='args')
    # - Begin shim -
    # Remove after folders and labels exposed in the Delta API for everybody,
    # right now, only expose for Edgehill.
    g.parser.add_argument('exclude_folders', type=strict_bool, location='args')
    # - End shim -

    args = strict_parse_args(g.parser, request.args)
    timeout = args['timeout'] or 1800
    transaction_pointer = None
    cursor = args['cursor']
    exclude_types = args.get('exclude_types')
    include_types = args.get('include_types')

    # Begin shim #
    exclude_folders = args.get('exclude_folders')
    if exclude_folders is None:
        exclude_folders = True
    # End shim #

    if include_types and exclude_types:
        return err(400, "Invalid Request. Cannot specify both include_types"
                   "and exclude_types")

    if cursor == '0':
        transaction_pointer = 0
    else:
        query_result = g.db_session.query(Transaction.id).filter(
            Transaction.namespace_id == g.namespace.id,
            Transaction.public_id == cursor).first()
        if query_result is None:
            raise InputError('Invalid cursor {}'.format(args['cursor']))
        transaction_pointer = query_result[0]

    # Hack to not keep a database session open for the entire (long) request
    # duration.
    g.db_session.expunge(g.namespace)
    g.db_session.close()
    # TODO make transaction log support the `expand` feature
    generator = delta_sync.streaming_change_generator(
        g.namespace, transaction_pointer=transaction_pointer,
        poll_interval=1, timeout=timeout, exclude_types=exclude_types,
        include_types=include_types, exclude_folders=exclude_folders)
    return Response(generator, mimetype='text/event-stream')


##
# Groups and Contact Rankings
##

@app.route('/groups/intrinsic')
def groups_intrinsic():
    g.parser.add_argument('force_recalculate', type=strict_bool,
                          location='args')
    args = strict_parse_args(g.parser, request.args)
    try:
        dpcache = g.db_session.query(DataProcessingCache).filter(
            DataProcessingCache.namespace_id == g.namespace.id).one()
    except NoResultFound:
        dpcache = DataProcessingCache(namespace_id=g.namespace.id)

    last_updated = dpcache.contact_groups_last_updated
    cached_data = dpcache.contact_groups

    use_cached_data = (not (is_stale(last_updated) or cached_data is None) and
                       args['force_recalculate'] is not True)

    if not use_cached_data:
        last_updated = None

    messages = filtering.messages_for_contact_scores(
        g.db_session, g.namespace.id, last_updated)

    from_email = g.namespace.email_address

    if use_cached_data:
        result = cached_data
        new_guys = calculate_group_counts(messages, from_email)
        for k, v in new_guys.items():
            if k in result:
                result[k] += v
            else:
                result[k] = v
    else:
        result = calculate_group_scores(messages, from_email)
        dpcache.contact_groups = result
        g.db_session.add(dpcache)
        g.db_session.commit()

    result = sorted(result.items(), key=lambda x: x[1], reverse=True)
    return g.encoder.jsonify(result)


@app.route('/contacts/rankings')
def contact_rankings():
    g.parser.add_argument('force_recalculate', type=strict_bool,
                          location='args')
    args = strict_parse_args(g.parser, request.args)
    try:
        dpcache = g.db_session.query(DataProcessingCache).filter(
            DataProcessingCache.namespace_id == g.namespace.id).one()
    except NoResultFound:
        dpcache = DataProcessingCache(namespace_id=g.namespace.id)

    last_updated = dpcache.contact_rankings_last_updated
    cached_data = dpcache.contact_rankings

    use_cached_data = (not (is_stale(last_updated) or cached_data is None) and
                       args['force_recalculate'] is not True)

    if not use_cached_data:
        last_updated = None

    messages = filtering.messages_for_contact_scores(
        g.db_session, g.namespace.id, last_updated)

    if use_cached_data:
        new_guys = calculate_contact_scores(messages, time_dependent=False)
        result = cached_data
        for k, v in new_guys.items():
            if k in result:
                result[k] += v
            else:
                result[k] = v
    else:
        result = calculate_contact_scores(messages)
        dpcache.contact_rankings = result
        g.db_session.add(dpcache)
        g.db_session.commit()

    result = sorted(result.items(), key=lambda x: x[1], reverse=True)
    return g.encoder.jsonify(result)
