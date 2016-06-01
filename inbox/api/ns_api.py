import base64
import copy
import os
import uuid
import gevent
import time
from datetime import datetime
import json

from flask import (request, g, Blueprint, make_response, Response,
                   stream_with_context)
from flask import jsonify as flask_jsonify
from flask.ext.restful import reqparse
from sqlalchemy import asc, func
from sqlalchemy.orm.exc import NoResultFound

from nylas.logging import get_logger
log = get_logger()
from inbox.models import (ApiThread, ApiMessage, Message, Block, Part, Thread, Namespace,
                          Contact, Calendar, Event, Transaction,
                          DataProcessingCache, Category, MessageCategory)
from inbox.models.event import RecurringEvent, RecurringEventOverride
from inbox.models.backends.generic import GenericAccount
from inbox.api.sending import send_draft, send_raw_mime
from inbox.api.update import update_message, update_thread
from inbox.api.kellogs import APIEncoder
from inbox.api import filtering
from inbox.api.validation import (valid_account, get_attachments, get_calendar,
                                  get_recipients, get_draft, valid_public_id,
                                  valid_event, valid_event_update, timestamp,
                                  bounded_str, view, strict_parse_args,
                                  limit, offset, ValidatableArgument,
                                  strict_bool, validate_draft_recipients,
                                  valid_delta_object_types, valid_display_name,
                                  noop_event_update, valid_category_type,
                                  comma_separated_email_list)
from inbox.config import config
from inbox.contacts.algorithms import (calculate_contact_scores,
                                       calculate_group_scores,
                                       calculate_group_counts, is_stale)
import inbox.contacts.crud
from inbox.contacts.search import ContactSearchClient
from inbox.sendmail.base import (create_message_from_json, update_draft,
                                 delete_draft, create_draft_from_mime,
                                 SendMailException)
from inbox.ignition import engine_manager
from inbox.models.action_log import schedule_action
from inbox.models.session import new_session, session_scope
from inbox.search.base import get_search_client, SearchBackendException
from inbox.transactions import delta_sync
from inbox.api.err import err, APIException, NotFoundError, InputError
from inbox.events.ical import (generate_icalendar_invite, send_invite,
                               generate_rsvp, send_rsvp)
from inbox.util.blockstore import get_from_blockstore

from inbox.api.api_store import ApiStore

DEFAULT_LIMIT = 100
MAX_LIMIT = 1000
LONG_POLL_REQUEST_TIMEOUT = 120
SEND_TIMEOUT = 60

app = Blueprint(
    'namespace_api',
    __name__,
    url_prefix='')

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
    from inbox.util.debug import attach_pyinstrument_profiler
    attach_pyinstrument_profiler()


@app.before_request
def start():
    engine = engine_manager.get_for_id(g.namespace_id)
    g.db_session = new_session(engine)
    g.namespace = Namespace.get(g.namespace_id, g.db_session)

    is_n1 = request.environ.get('IS_N1', False)
    g.encoder = APIEncoder(g.namespace.public_id, is_n1=is_n1)

    g.log = log.new(endpoint=request.endpoint,
                    account_id=g.namespace.account_id)
    g.parser = reqparse.RequestParser(argument_class=ValidatableArgument)
    g.parser.add_argument('limit', default=DEFAULT_LIMIT, type=limit,
                          location='args')
    g.parser.add_argument('offset', default=0, type=offset, location='args')

    g.api_store = ApiStore(g.db_session, g.log)


@app.before_request
def before_remote_request():
    """
    Verify the validity of the account's credentials before performing a
    request to the remote server.

    The message and thread /search endpoints, and the /send endpoint directly
    interact with the remote server. All create, update, delete requests
    result in requests to the remote server via action syncback.

    """
    # Search uses 'GET', all the other requests we care about use a write
    # HTTP method.
    if (request.endpoint in ('namespace_api.message_search_api',
                             'namespace_api.thread_search_api',
                             'namespace_api.message_streaming_search_api',
                             'namespace_api.thread_streaming_search_api') or
            request.method in ('POST', 'PUT', 'PATCH', 'DELETE')):
        valid_account(g.namespace)


@app.after_request
def finish(response):
    if response.status_code == 200 and hasattr(g, 'db_session'):  # be cautions
        g.db_session.commit()
    if hasattr(g, 'db_session'):
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
    log.info('Returning API error to client', error=error)
    response = flask_jsonify(message=error.message,
                             type='invalid_request_error')
    response.status_code = error.status_code
    return response


@app.route('/account')
def one_account():
    g.parser.add_argument('view', type=view, location='args')
    args = strict_parse_args(g.parser, request.args)
    # Use a new encoder object with the expand parameter set.
    encoder = APIEncoder(g.namespace.public_id, args['view'] == 'expanded')
    return encoder.jsonify(g.namespace)


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
    g.parser.add_argument('any_email', type=comma_separated_email_list,
                          location='args')
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
        unread=args['unread'],
        starred=args['starred'],
        in_=args['in'],
        limit=args['limit'],
        offset=args['offset'],
        view=args['view'],
        db_session=g.db_session)

    # Use a new encoder object with the expand parameter set.
    encoder = APIEncoder(g.namespace.public_id,
                         args['view'] == 'expanded')
    return encoder.jsonify(threads)


@app.route('/threads/search', methods=['GET'])
def thread_search_api():
    g.parser.add_argument('q', type=bounded_str, location='args')
    args = strict_parse_args(g.parser, request.args)
    if not args['q']:
        err_string = ('GET HTTP method must include query'
                      ' url parameter')
        g.log.error(err_string)
        return err(400, err_string)

    try:
        search_client = get_search_client(g.namespace.account)
        results = search_client.search_threads(g.db_session, args['q'],
                                               offset=args['offset'],
                                               limit=args['limit'])
        return g.encoder.jsonify(results)
    except SearchBackendException as exc:
        kwargs = {}
        if exc.server_error:
            kwargs['server_error'] = exc.server_error
        return err(exc.http_code, exc.message, **kwargs)


@app.route('/threads/search/streaming', methods=['GET'])
def thread_streaming_search_api():
    g.parser.add_argument('q', type=bounded_str, location='args')
    args = strict_parse_args(g.parser, request.args)
    if not args['q']:
        err_string = ('GET HTTP method must include query'
                      ' url parameter')
        g.log.error(err_string)
        return err(400, err_string)

    try:
        search_client = get_search_client(g.namespace.account)
        generator = search_client.stream_threads(args['q'])

        return Response(stream_with_context(generator()),
                        mimetype='text/json-stream')
    except SearchBackendException as exc:
        kwargs = {}
        if exc.server_error:
            kwargs['server_error'] = exc.server_error
        return err(exc.http_code, exc.message, **kwargs)


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
@app.route('/threads/<public_id>', methods=['PUT', 'PATCH'])
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
    g.parser.add_argument('any_email', type=comma_separated_email_list,
                          location='args')
    g.parser.add_argument('started_before', type=timestamp, location='args')
    g.parser.add_argument('started_after', type=timestamp, location='args')
    g.parser.add_argument('last_message_before', type=timestamp,
                          location='args')
    g.parser.add_argument('last_message_after', type=timestamp,
                          location='args')
    g.parser.add_argument('received_before', type=timestamp,
                          location='args')
    g.parser.add_argument('received_after', type=timestamp,
                          location='args')
    g.parser.add_argument('filename', type=bounded_str, location='args')
    g.parser.add_argument('in', type=bounded_str, location='args')
    g.parser.add_argument('thread_id', type=valid_public_id, location='args')
    g.parser.add_argument('unread', type=strict_bool, location='args')
    g.parser.add_argument('starred', type=strict_bool, location='args')
    g.parser.add_argument('view', type=view, location='args')

    args = strict_parse_args(g.parser, request.args)

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
        received_before=args['received_before'],
        received_after=args['received_after'],
        filename=args['filename'],
        in_=args['in'],
        unread=args['unread'],
        starred=args['starred'],
        limit=args['limit'],
        offset=args['offset'],
        view=args['view'],
        db_session=g.db_session)

    # Use a new encoder object with the expand parameter set.
    encoder = APIEncoder(g.namespace.public_id, args['view'] == 'expanded')
    return encoder.jsonify(messages)


@app.route('/messages/search', methods=['GET'])
def message_search_api():
    g.parser.add_argument('q', type=bounded_str, location='args')
    args = strict_parse_args(g.parser, request.args)
    if not args['q']:
        err_string = ('GET HTTP method must include query'
                      ' url parameter')
        g.log.error(err_string)
        return err(400, err_string)

    try:
        search_client = get_search_client(g.namespace.account)
        results = search_client.search_messages(g.db_session, args['q'],
                                                offset=args['offset'],
                                                limit=args['limit'])
        return g.encoder.jsonify(results)
    except SearchBackendException as exc:
        kwargs = {}
        if exc.server_error:
            kwargs['server_error'] = exc.server_error
        return err(exc.http_code, exc.message, **kwargs)


@app.route('/messages/search/streaming', methods=['GET'])
def message_streaming_search_api():
    g.parser.add_argument('q', type=bounded_str, location='args')
    args = strict_parse_args(g.parser, request.args)
    if not args['q']:
        err_string = ('GET HTTP method must include query'
                      ' url parameter')
        g.log.error(err_string)
        return err(400, err_string)

    try:
        search_client = get_search_client(g.namespace.account)
        generator = search_client.stream_messages(args['q'])

        return Response(stream_with_context(generator()),
                        mimetype='text/json-stream')
    except SearchBackendException as exc:
        kwargs = {}
        if exc.server_error:
            kwargs['server_error'] = exc.server_error
        return err(exc.http_code, exc.message, **kwargs)


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
        raise NotFoundError("Couldn't find message {0}".format(public_id))

    if request.headers.get('Accept', None) == 'message/rfc822':
        raw_message = get_from_blockstore(message.data_sha256)
        if raw_message is not None:
            return Response(raw_message, mimetype='message/rfc822')
        else:
            g.log.error('Missing raw MIME message', id=message.id)
            raise NotFoundError(
                "Couldn't find raw contents for message `{0}`"
                .format(public_id))

    return encoder.jsonify(message)


EPOCH = datetime.utcfromtimestamp(0)

def _dumps(obj):
    def serialize_with_epoch_time(obj):
        if isinstance(obj, datetime):
            epoch_seconds = (obj - EPOCH).total_seconds()
            return epoch_seconds
        raise TypeError('Type not serializable')
    return json.dumps(obj, default=serialize_with_epoch_time)


@app.route('/messages2/<public_id>', methods=['GET'])
def message2_read_api(public_id):
    g.parser.add_argument('view', type=view, location='args')
    args = strict_parse_args(g.parser, request.args)

    try:
        valid_public_id(public_id)

        message = g.api_store.get_with_patch(g.namespace.id, ApiMessage, public_id)
        # TODO data_sha256 will break

        if request.headers.get('Accept', None) == 'message/rfc822':
            raw_message = get_from_blockstore(message.data_sha256)
            if raw_message is not None:
                return Response(raw_message, mimetype='message/rfc822')
            else:
                g.log.error('Missing raw MIME message', id=message.id)
                raise NotFoundError(
                    "Couldn't find raw contents for message `{0}`"
                    .format(public_id))

        json = message.as_json(view=args['view'])

        return Response(json, mimetype='application/json')
    except KeyError:
        raise NotFoundError("Couldn't find message {0} ".format(public_id))


def _jsons_to_list(jsons):
    return '[' + ','.join(jsons) + ']'


@app.route('/messages2/', methods=['GET'])
def message2_query_api():
    g.parser.add_argument('view', type=view, location='args')
    g.parser.add_argument('in', type=bounded_str, location='args')
    g.parser.add_argument('subject', type=bounded_str, location='args')
    g.parser.add_argument('thread_id', type=valid_public_id, location='args')

    args = strict_parse_args(g.parser, request.args)

    messages = g.api_store.all(g.namespace.id, ApiMessage,
            limit=args['limit'],
            offset=args['offset'],
            in_=args['in'],
            subject=args['subject'],
            thread_public_id=args['thread_id'])

    json = _jsons_to_list(m.as_json(view=args['view']) for m in messages)
    return Response(json, mimetype='application/json')


@app.route('/threads2/<public_id>')
def thread2_api(public_id):
    g.parser.add_argument('view', type=view, location='args')
    args = strict_parse_args(g.parser, request.args)

    try:
        valid_public_id(public_id)
        thread = g.api_store.get_with_patch(g.namespace.id, ApiThread, public_id)

        json = thread.as_json(view=args['view'])

        return Response(json, mimetype='application/json')
    except KeyError:
        raise NotFoundError("Couldn't find thread `{0}`".format(public_id))


@app.route('/threads2/', methods=['GET'])
def thread2_query_api():
    g.parser.add_argument('view', type=view, location='args')
    g.parser.add_argument('in', type=bounded_str, location='args')
    g.parser.add_argument('subject', type=bounded_str, location='args')
    g.parser.add_argument('thread_id', type=valid_public_id, location='args')

    args = strict_parse_args(g.parser, request.args)

    threads = g.api_store.all(g.namespace.id, ApiThread,
            limit=args['limit'],
            offset=args['offset'],
            in_=args['in'],
            subject=args['subject'],
            thread_public_id=args['thread_id'])

    json = _jsons_to_list(t.as_json(view=args['view']) for t in threads)
    return Response(json, mimetype='application/json')


@app.route('/messages/<public_id>', methods=['PUT', 'PATCH'])
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

    # Take a copy of the message so our updates don't get saved to the sync DB
    # TODO is this a safe way of copying the message?
    updated_message = copy.copy(message)
    update_message(updated_message, data, g.db_session)
    return g.encoder.jsonify(updated_message)


# Folders / Labels
@app.route('/folders')
@app.route('/labels')
def folders_labels_query_api():
    category_type = g.namespace.account.category_type
    rule = request.url_rule.rule
    valid_category_type(category_type, rule)

    g.parser.add_argument('view', type=bounded_str, location='args')
    args = strict_parse_args(g.parser, request.args)
    if args['view'] == 'count':
        results = g.db_session.query(func.count(Category.id))
    elif args['view'] == 'ids':
        results = g.db_session.query(Category.public_id)
    else:
        results = g.db_session.query(Category)

    results = results.filter(Category.namespace_id == g.namespace.id,
                             Category.deleted_at == None)  # noqa
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
    category_type = g.namespace.account.category_type
    rule = request.url_rule.rule
    valid_category_type(category_type, rule)
    valid_public_id(public_id)
    try:
        category = g.db_session.query(Category).filter(
            Category.namespace_id == g.namespace.id,
            Category.public_id == public_id,
            Category.deleted_at == None).one()  # noqa
    except NoResultFound:
        raise NotFoundError('Object not found')
    return g.encoder.jsonify(category)


@app.route('/folders', methods=['POST'])
@app.route('/labels', methods=['POST'])
def folders_labels_create_api():
    category_type = g.namespace.account.category_type
    rule = request.url_rule.rule
    valid_category_type(category_type, rule)
    data = request.get_json(force=True)
    display_name = data.get('display_name')

    valid_display_name(g.namespace.id, category_type, display_name,
                       g.db_session)

    # We do not allow creating a category with the same name as a
    # deleted category /until/ the corresponding folder/label
    # delete syncback is performed. This is a limitation but is the
    # simplest way to prevent the creation of categories with duplicate
    # names; it also hinders creation in the one case only (namely,
    # delete category with display_name "x" via the API -> quickly
    # try to create a category with the same display_name).
    category = g.db_session.query(Category).filter(
        Category.namespace_id == g.namespace.id,
        Category.name == None,  # noqa
        Category.display_name == display_name,
        Category.type_ == category_type).first()

    if category:
        return err(403, "{} with name {} already exists".
                        format(category_type, display_name))

    category = Category.find_or_create(g.db_session, g.namespace.id,
                                       name=None, display_name=display_name,
                                       type_=category_type)
    if category.deleted_at:
        category = Category(namespace_id=g.namespace.id, name=None,
                            display_name=display_name, type_=category_type)
        g.db_session.add(category)
    g.db_session.flush()

    if category_type == 'folder':
        schedule_action('create_folder', category, g.namespace.id,
                        g.db_session)
    else:
        schedule_action('create_label', category, g.namespace.id, g.db_session)

    return g.encoder.jsonify(category)


@app.route('/folders/<public_id>', methods=['PUT', 'PATCH'])
@app.route('/labels/<public_id>', methods=['PUT', 'PATCH'])
def folder_label_update_api(public_id):
    category_type = g.namespace.account.category_type
    rule = request.url_rule.rule
    valid_category_type(category_type, rule)
    valid_public_id(public_id)
    try:
        category = g.db_session.query(Category).filter(
            Category.namespace_id == g.namespace.id,
            Category.public_id == public_id,
            Category.deleted_at == None).one()  # noqa
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


@app.route('/folders/<public_id>', methods=['DELETE'])
@app.route('/labels/<public_id>', methods=['DELETE'])
def folder_label_delete_api(public_id):
    category_type = g.namespace.account.category_type
    rule = request.url_rule.rule
    valid_category_type(category_type, rule)
    valid_public_id(public_id)
    try:
        category = g.db_session.query(Category).filter(
            Category.namespace_id == g.namespace.id,
            Category.public_id == public_id,
            Category.deleted_at == None).one()  # noqa
    except NoResultFound:
        raise InputError("Couldn't find {} {}".format(
            category_type, public_id))
    if category.name is not None:
        raise InputError("Cannot modify a standard {}".format(category_type))

    if category.type_ == 'folder':
        messages_with_category = g.db_session.query(MessageCategory).filter(
            MessageCategory.category_id == category.id).exists()
        messages_exist = g.db_session.query(messages_with_category).scalar()
        if messages_exist:
            raise InputError(
                "Folder {} cannot be deleted because it contains messages.".
                format(public_id))

        deleted_at = datetime.utcnow()
        category.deleted_at = deleted_at
        folders = category.folders if g.namespace.account.discriminator != 'easaccount' \
            else category.easfolders
        for folder in folders:
            folder.deleted_at = deleted_at

        schedule_action('delete_folder', category, g.namespace.id,
                        g.db_session)
    else:
        deleted_at = datetime.utcnow()
        category.deleted_at = deleted_at
        for label in category.labels:
            label.deleted_at = deleted_at

        schedule_action('delete_label', category, g.namespace.id,
                        g.db_session)

    g.db_session.commit()

    return g.encoder.jsonify(None)


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
    results = results.with_hint(
        Contact, 'USE INDEX (ix_contact_ns_uid_provider_name)')\
        .order_by(asc(Contact.created_at))

    if args['view'] == 'count':
        return g.encoder.jsonify({"count": results.scalar()})

    results = results.limit(args['limit']).offset(args['offset']).all()
    if args['view'] == 'ids':
        return g.encoder.jsonify([r for r, in results])

    return g.encoder.jsonify(results)


@app.route('/contacts/search', methods=['GET'])
def contact_search_api():
    g.parser.add_argument('q', type=bounded_str, location='args')
    args = strict_parse_args(g.parser, request.args)
    if not args['q']:
        err_string = ('GET HTTP method must include query'
                      ' url parameter')
        g.log.error(err_string)
        return err(400, err_string)

    search_client = ContactSearchClient(g.namespace.id)
    results = search_client.search_contacts(g.db_session, args['q'],
                                            offset=args['offset'],
                                            limit=args['limit'])
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


@app.route('/events/<public_id>', methods=['PUT', 'PATCH'])
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

    for attr in Event.API_MODIFIABLE_FIELDS:
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

    p = participants[email]

    # Make this API idempotent.
    if p["status"] == status:
        if 'comment' not in p and 'comment' not in data:
            return g.encoder.jsonify(event)
        elif ('comment' in p and 'comment' in data and
              p['comment'] == data['comment']):
            return g.encoder.jsonify(event)

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
        name = '=?utf-8?b?' + base64.b64encode(name.encode('utf-8')) + '?='
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
    g.parser.add_argument('any_email', type=comma_separated_email_list,
                          location='args')
    g.parser.add_argument('started_before', type=timestamp, location='args')
    g.parser.add_argument('started_after', type=timestamp, location='args')
    g.parser.add_argument('last_message_before', type=timestamp,
                          location='args')
    g.parser.add_argument('last_message_after', type=timestamp,
                          location='args')
    g.parser.add_argument('received_before', type=timestamp,
                          location='args')
    g.parser.add_argument('received_after', type=timestamp,
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
        received_before=args['received_before'],
        received_after=args['received_after'],
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
    draft = create_message_from_json(data, g.namespace, g.db_session,
                                     is_draft=True)
    return g.encoder.jsonify(draft)


@app.route('/drafts/<public_id>', methods=['PUT', 'PATCH'])
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
    request_started = time.time()
    account = g.namespace.account
    if request.content_type == "message/rfc822":
        draft = create_draft_from_mime(account, request.data,
                                       g.db_session)
        validate_draft_recipients(draft)
        if isinstance(account, GenericAccount):
            schedule_action('save_sent_email', draft, draft.namespace.id,
                            g.db_session)
        resp = send_raw_mime(account, g.db_session, draft)
        return resp

    data = request.get_json(force=True)
    draft_public_id = data.get('draft_id')
    if draft_public_id is not None:
        draft = get_draft(draft_public_id, data.get('version'),
                          g.namespace.id, g.db_session)
        schedule_action('delete_draft', draft, draft.namespace.id,
                        g.db_session, inbox_uid=draft.inbox_uid,
                        message_id_header=draft.message_id_header)
    else:
        draft = create_message_from_json(data, g.namespace,
                                         g.db_session, is_draft=False)
    validate_draft_recipients(draft)
    if isinstance(account, GenericAccount):
        schedule_action('save_sent_email', draft, draft.namespace.id,
                        g.db_session)
    if time.time() - request_started > SEND_TIMEOUT:
        # Preemptively time out the request if we got stuck doing database work
        # -- we don't want clients to disconnect and then still send the
        # message.
        return err(504, 'Request timed out.')

    resp = send_draft(account, draft, g.db_session)
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
    g.parser.add_argument('view', type=view, location='args')
    # - Begin shim -
    # Remove after folders and labels exposed in the Delta API for everybody,
    # right now, only expose for Edgehill.
    # Same for the account object.
    g.parser.add_argument('exclude_folders', type=strict_bool, location='args')
    g.parser.add_argument('exclude_account', type=strict_bool, location='args',
                          default=True)
    # - End shim -
    # Metadata has restricted access - only N1 can make a request with this
    # arg included. For everyone else, set exclude_metadata to True by default.
    g.parser.add_argument('exclude_metadata', type=strict_bool,
                          location='args', default=True)
    args = strict_parse_args(g.parser, request.args)
    exclude_types = args.get('exclude_types')
    include_types = args.get('include_types')
    expand = args.get('view') == 'expanded'
    exclude_metadata = args.get('exclude_metadata')
    # - Begin shim -
    exclude_folders = args.get('exclude_folders')
    if exclude_folders is None:
        exclude_folders = True
    exclude_account = args.get('exclude_account')
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
        with session_scope(g.namespace.id) as db_session:
            deltas, _ = delta_sync.format_transactions_after_pointer(
                g.namespace, start_pointer, db_session, args['limit'],
                exclude_types, include_types, exclude_folders,
                exclude_metadata, exclude_account, expand=expand)

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


# TODO Deprecate this
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


@app.route('/delta/latest_cursor', methods=['POST'])
def latest_cursor():
    cursor = delta_sync.get_transaction_cursor_near_timestamp(
        g.namespace.id,
        int(time.time()),
        g.db_session)
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
    g.parser.add_argument('view', type=view, location='args')
    # - Begin shim -
    # Remove after folders and labels exposed in the Delta API for everybody,
    # right now, only expose for Edgehill.
    # Same for the account object.
    g.parser.add_argument('exclude_folders', type=strict_bool, location='args')
    g.parser.add_argument('exclude_account', type=strict_bool, location='args',
                          default=True)
    # - End shim -
    # Metadata has restricted access - only N1 can make a request with this
    # arg included. For everyone else, set exclude_metadata to True by default.
    g.parser.add_argument('exclude_metadata', type=strict_bool,
                          location='args', default=True)

    args = strict_parse_args(g.parser, request.args)
    timeout = args['timeout'] or 1800
    transaction_pointer = None
    cursor = args['cursor']
    exclude_types = args.get('exclude_types')
    include_types = args.get('include_types')
    expand = args.get('view') == 'expanded'
    exclude_metadata = args.get('exclude_metadata')

    # Begin shim #
    exclude_folders = args.get('exclude_folders')
    if exclude_folders is None:
        exclude_folders = True
    exclude_account = args.get('exclude_account')
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

    poll_interval = config.get('STREAMING_API_POLL_INTERVAL', 1)
    # TODO make transaction log support the `expand` feature

    is_n1 = request.environ.get('IS_N1', False)
    generator = delta_sync.streaming_change_generator(
        g.namespace, transaction_pointer=transaction_pointer,
        poll_interval=poll_interval, timeout=timeout,
        exclude_types=exclude_types, include_types=include_types,
        exclude_folders=exclude_folders,
        exclude_metadata=exclude_metadata, exclude_account=exclude_account,
        expand=expand, is_n1=is_n1)
    return Response(stream_with_context(generator),
                    mimetype='text/event-stream')


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
