import os
import base64

from datetime import datetime
from flask import request, g, Blueprint, make_response, Response
from flask import jsonify as flask_jsonify
from flask.ext.restful import reqparse
from sqlalchemy import asc, or_, func
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm import subqueryload

from inbox.models import (Message, Block, Part, Thread, Namespace,
                          Tag, Contact, Calendar, Event, Transaction)
from inbox.api.kellogs import APIEncoder
from inbox.api import filtering
from inbox.api.validation import (InputError, get_tags, get_attachments,
                                  get_calendar, get_thread, get_recipients,
                                  valid_public_id, valid_event,
                                  valid_event_update, timestamp, boolean,
                                  bounded_str, view, strict_parse_args, limit,
                                  valid_event_action, valid_rsvp,
                                  ValidatableArgument,
                                  validate_draft_recipients,
                                  validate_search_query,
                                  valid_delta_object_types)
from inbox import events, contacts, sendmail
from inbox.log import get_logger
from inbox.models.constants import MAX_INDEXABLE_LENGTH
from inbox.models.action_log import schedule_action, ActionError
from inbox.models.session import InboxSession
from inbox.search.adaptor import NamespaceSearchEngine, SearchEngineError
from inbox.sendmail import rate_limited
from inbox.transactions import delta_sync

from err import err

from inbox.ignition import main_engine
engine = main_engine()


DEFAULT_LIMIT = 100
MAX_LIMIT = 1000


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


@app.url_value_preprocessor
def pull_lang_code(endpoint, values):
    g.namespace_public_id = values.pop('namespace_public_id')


@app.before_request
def start():
    g.db_session = InboxSession(engine)

    g.log = get_logger()
    try:
        valid_public_id(g.namespace_public_id)
        g.namespace = g.db_session.query(Namespace) \
            .filter(Namespace.public_id == g.namespace_public_id).one()

        g.encoder = APIEncoder(g.namespace.public_id)
    except (NoResultFound, InputError):
        return err(404, "Couldn't find namespace with id `{0}` ".format(
            g.namespace_public_id))

    g.parser = reqparse.RequestParser(argument_class=ValidatableArgument)
    g.parser.add_argument('limit', default=DEFAULT_LIMIT, type=limit,
                          location='args')
    g.parser.add_argument('offset', default=0, type=int, location='args')


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


@app.errorhandler(InputError)
def handle_input_error(error):
    response = flask_jsonify(message=str(error), type='api_error')
    response.status_code = 400
    return response


#
# General namespace info
#
@app.route('/')
def index():
    return g.encoder.jsonify(g.namespace)


##
# Tags
##
@app.route('/tags/')
def tag_query_api():
    g.parser.add_argument('tag_name', type=bounded_str, location='args')
    g.parser.add_argument('tag_id', type=valid_public_id, location='args')
    g.parser.add_argument('view', type=view, location='args')

    args = strict_parse_args(g.parser, request.args)

    if args['view'] == 'count':
        query = g.db_session.query(func.count(Tag.id))
    elif args['view'] == 'ids':
        query = g.db_session.query(Tag.public_id)
    else:
        query = g.db_session.query(Tag)

    query = query.filter(Tag.namespace_id == g.namespace.id)

    if args['tag_name']:
        query = query.filter_by(name=args['tag_name'])

    if args['tag_id']:
        query = query.filter_by(public_id=args['tag_id'])

    if args['view'] == 'count':
        return g.encoder.jsonify({"count": query.one()[0]})

    query = query.order_by(Tag.id)
    query = query.limit(args['limit'])
    if args['offset']:
        query = query.offset(args['offset'])

    if args['view'] == 'ids':
        results = [x[0] for x in query.all()]
    else:
        results = query.all()

    return g.encoder.jsonify(results)


@app.route('/tags/<public_id>', methods=['GET'])
def tag_read_api(public_id):
    try:
        valid_public_id(public_id)
        tag = g.db_session.query(Tag).filter(
            Tag.public_id == public_id,
            Tag.namespace_id == g.namespace.id).one()
    except InputError:
        return err(400, '{} is not a valid id'.format(public_id))
    except NoResultFound:
        return err(404, 'No tag found')

    return g.encoder.jsonify(tag)


@app.route('/tags/<public_id>', methods=['PUT'])
def tag_update_api(public_id):
    try:
        valid_public_id(public_id)
        tag = g.db_session.query(Tag).filter(
            Tag.public_id == public_id,
            Tag.namespace_id == g.namespace.id).one()
    except InputError:
        return err(400, '{} is not a valid id'.format(public_id))
    except NoResultFound:
        return err(404, 'No tag found')

    data = request.get_json(force=True)
    if not ('name' in data.keys() and isinstance(data['name'], basestring)):
        return err(400, 'Malformed tag update request')
    if 'namespace_id' in data.keys():
        ns_id = data['namespace_id']
        valid_public_id(ns_id)
        if ns_id != g.namespace.id:
            return err(400, 'Cannot change the namespace on a tag.')
    if not tag.user_created:
        return err(403, 'Cannot modify tag {}'.format(public_id))
    # Lowercase tag name, regardless of input casing.
    new_name = data['name'].lower()

    if new_name != tag.name:  # short-circuit rename to same value
        if not Tag.name_available(new_name, g.namespace.id, g.db_session):
            return err(409, 'Tag name already used')
        tag.name = new_name
        g.db_session.commit()

    return g.encoder.jsonify(tag)


@app.route('/tags/', methods=['POST'])
def tag_create_api():
    data = request.get_json(force=True)
    if not ('name' in data.keys() and isinstance(data['name'], basestring)):
        return err(400, 'Malformed tag request')
    if 'namespace_id' in data.keys():
        ns_id = data['namespace_id']
        valid_public_id(ns_id)
        if ns_id != g.namespace.id:
            return err(400, 'Cannot change the namespace on a tag.')
    # Lowercase tag name, regardless of input casing.
    tag_name = data['name'].lower()
    if not Tag.name_available(tag_name, g.namespace.id, g.db_session):
        return err(409, 'Tag name not available')
    if len(tag_name) > MAX_INDEXABLE_LENGTH:
        return err(400, 'Tag name is too long.')

    tag = Tag(name=tag_name, namespace=g.namespace, user_created=True)
    g.db_session.commit()
    return g.encoder.jsonify(tag)


@app.route('/tags/<public_id>', methods=['DELETE'])
def tag_delete_api(public_id):
    try:
        valid_public_id(public_id)
        t = g.db_session.query(Tag).filter(
            Tag.public_id == public_id).one()

        if not t.user_created:
            return err(400, "Can't delete non user-created tag.")

        g.db_session.delete(t)
        g.db_session.commit()

        # This is essentially what our other API endpoints do after deleting.
        # Effectively no error == success
        return g.encoder.jsonify(None)
    except InputError:
        return err(400, 'Invalid tag id {}'.format(public_id))
    except NoResultFound:
        return err(404, "Couldn't find tag with id {0} "
                   "on namespace {1}".format(public_id, g.namespace_public_id))


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
    g.parser.add_argument('thread_id', type=valid_public_id, location='args')
    g.parser.add_argument('tag', type=bounded_str, location='args')
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
        tag=args['tag'],
        limit=args['limit'],
        offset=args['offset'],
        view=args['view'],
        db_session=g.db_session)

    return g.encoder.jsonify(threads)


@app.route('/threads/search', methods=['POST'])
def thread_search_api():
    args = strict_parse_args(g.parser, request.args)
    data = request.get_json(force=True)
    query = data.get('query')

    validate_search_query(query)

    try:
        search_engine = NamespaceSearchEngine(g.namespace_public_id)
        results = search_engine.threads.search(query=query,
                                               max_results=args.limit,
                                               offset=args.offset)
    except SearchEngineError as e:
        g.log.error('Search error: {0}'.format(e))
        return err(501, 'Search error')

    return g.encoder.jsonify(results)


@app.route('/threads/<public_id>')
def thread_api(public_id):
    try:
        valid_public_id(public_id)
        thread = g.db_session.query(Thread).filter(
            Thread.public_id == public_id,
            Thread.namespace_id == g.namespace.id).one()
        return g.encoder.jsonify(thread)
    except InputError:
        return err(400, 'Invalid thread id {}'.format(public_id))
    except NoResultFound:
        return err(404, "Couldn't find thread with id `{0}` "
                   "on namespace {1}".format(public_id, g.namespace_public_id))


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
    except InputError:
        return err(400, 'Invalid thread id {}'.format(public_id))
    except NoResultFound:
        return err(404, "Couldn't find thread with id `{0}` "
                   "on namespace {1}".format(public_id, g.namespace_public_id))
    data = request.get_json(force=True)
    if not set(data).issubset({'add_tags', 'remove_tags'}):
        return err(400, 'Can only add or remove tags from thread.')

    removals = data.get('remove_tags', [])

    for tag_identifier in removals:
        tag = g.db_session.query(Tag).filter(
            Tag.namespace_id == g.namespace.id,
            or_(Tag.public_id == tag_identifier,
                Tag.name == tag_identifier)).first()
        if tag is None:
            return err(404, 'No tag found with name {}'.format(tag_identifier))
        if not tag.user_removable:
            return err(400, 'Cannot remove tag {}'.format(tag_identifier))

        try:
            thread.remove_tag(tag, execute_action=True)
        except ActionError as e:
            return err(e.error, str(e))

    additions = data.get('add_tags', [])
    for tag_identifier in additions:
        tag = g.db_session.query(Tag).filter(
            Tag.namespace_id == g.namespace.id,
            or_(Tag.public_id == tag_identifier,
                Tag.name == tag_identifier)).first()
        if tag is None:
            return err(404, 'No tag found with name {}'.format(tag_identifier))
        if not tag.user_addable:
            return err(400, 'Cannot add tag {}'.format(tag_identifier))

        try:
            thread.apply_tag(tag, execute_action=True)
        except ActionError as e:
            return err(e.error, str(e))

    g.db_session.commit()
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
    g.parser.add_argument('thread_id', type=valid_public_id, location='args')
    g.parser.add_argument('tag', type=bounded_str, location='args')
    g.parser.add_argument('view', type=view, location='args')
    args = strict_parse_args(g.parser, request.args)
    messages = filtering.messages(
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
        tag=args['tag'],
        limit=args['limit'],
        offset=args['offset'],
        view=args['view'],
        db_session=g.db_session)

    return g.encoder.jsonify(messages)


@app.route('/messages/search', methods=['POST'])
def message_search_api():
    args = strict_parse_args(g.parser, request.args)
    data = request.get_json(force=True)
    query = data.get('query')

    validate_search_query(query)

    try:
        search_engine = NamespaceSearchEngine(g.namespace_public_id)
        results = search_engine.messages.search(query=query,
                                                max_results=args.limit,
                                                offset=args.offset)
    except SearchEngineError as e:
        g.log.error('Search error: {0}'.format(e))
        return err(501, 'Search error')

    return g.encoder.jsonify(results)


@app.route('/messages/<public_id>', methods=['GET', 'PUT'])
def message_api(public_id):
    try:
        valid_public_id(public_id)
        message = g.db_session.query(Message).filter(
            Message.public_id == public_id,
            Message.namespace_id == g.namespace.id).one()
    except InputError:
        return err(400, 'Invalid message id {}'.format(public_id))
    except NoResultFound:
        return err(404,
                   "Couldn't find message with id {0} "
                   "on namespace {1}".format(public_id, g.namespace_public_id))
    if request.method == 'GET':
        return g.encoder.jsonify(message)
    elif request.method == 'PUT':
        data = request.get_json(force=True)
        if data.keys() != ['unread'] or not isinstance(data['unread'], bool):
            return err(400,
                       'Can only change the unread attribute of a message')

        # TODO(emfree): Shouldn't allow this on messages that are actually
        # drafts.

        unread_tag = message.namespace.tags['unread']
        unseen_tag = message.namespace.tags['unseen']
        if data['unread']:
            message.is_read = False
            message.thread.apply_tag(unread_tag)
        else:
            message.is_read = True
            message.thread.remove_tag(unseen_tag)
            if all(m.is_read for m in message.thread.messages):
                message.thread.remove_tag(unread_tag)
        return g.encoder.jsonify(message)


@app.route('/messages/<public_id>/rfc2822', methods=['GET'])
def raw_message_api(public_id):
    try:
        valid_public_id(public_id)
        message = g.db_session.query(Message).filter(
            Message.public_id == public_id,
            Message.namespace_id == g.namespace.id).one()
    except InputError:
        return err(400, 'Invalid message id {}'.format(public_id))
    except NoResultFound:
        return err(404,
                   "Couldn't find raw message with id {0} "
                   "on namespace {1}".format(public_id, g.namespace_public_id))

    if message.full_body is None:
        return err(404,
                   "Couldn't find raw message with id {0} "
                   "on namespace {1}".format(public_id, g.namespace_public_id))

    b64_contents = base64.b64encode(message.full_body.data)
    return g.encoder.jsonify({"rfc2822": b64_contents})


#
# Contacts
##
@app.route('/contacts/', methods=['GET'])
def contact_search_api():
    g.parser.add_argument('filter', type=bounded_str, default='',
                          location='args')
    g.parser.add_argument('view', type=bounded_str, location='args')

    args = strict_parse_args(g.parser, request.args)
    term_filter_string = '%{}%'.format(args['filter'])
    term_filter = or_(
        Contact.name.like(term_filter_string),
        Contact.email_address.like(term_filter_string))

    if args['view'] == 'count':
        results = g.db_session.query(func.count(Contact.id))
    elif args['view'] == 'ids':
        results = g.db_session.query(Contact.id)
    else:
        results = g.db_session.query(Contact)

    results = results.filter(Contact.namespace_id == g.namespace.id,
                             Contact.source == 'local',
                             term_filter).order_by(asc(Contact.id))

    if args['view'] == 'count':
        return g.encoder.jsonify({"count": results.all()})

    results = results.limit(args['limit']).offset(args['offset']).all()
    return g.encoder.jsonify(results)


@app.route('/contacts/', methods=['POST'])
def contact_create_api():
    # TODO(emfree) Detect attempts at duplicate insertions.
    data = request.get_json(force=True)
    name = data.get('name')
    email = data.get('email')
    if not any((name, email)):
        return err(400, 'Contact name and email cannot both be null.')
    new_contact = contacts.crud.create(g.namespace, g.db_session,
                                       name, email)
    return g.encoder.jsonify(new_contact)


@app.route('/contacts/<public_id>', methods=['GET'])
def contact_read_api(public_id):
    try:
        valid_public_id(public_id)
    except InputError:
        return err(400, 'Invalid contact id {}'.format(public_id))
    # TODO auth with account object
    # Get all data for an existing contact.
    result = contacts.crud.read(g.namespace, g.db_session, public_id)
    if result is None:
        return err(404, "Couldn't find contact with id {0}".
                   format(public_id))
    return g.encoder.jsonify(result)


@app.route('/contacts/<public_id>', methods=['PUT'])
def contact_update_api(public_id):
    raise NotImplementedError


@app.route('/contacts/<public_id>', methods=['DELETE'])
def contact_delete_api(public_id):
    raise NotImplementedError


##
# Events
##
@app.route('/events/', methods=['GET'])
def event_search_api():
    g.parser.add_argument('event_id', type=valid_public_id, location='args')
    g.parser.add_argument('calendar_id', type=valid_public_id, location='args')
    g.parser.add_argument('title', type=bounded_str, location='args')
    g.parser.add_argument('description', type=bounded_str, location='args')
    g.parser.add_argument('location', type=bounded_str, location='args')
    g.parser.add_argument('starts_before', type=timestamp, location='args')
    g.parser.add_argument('starts_after', type=timestamp, location='args')
    g.parser.add_argument('ends_before', type=timestamp, location='args')
    g.parser.add_argument('ends_after', type=timestamp, location='args')
    g.parser.add_argument('view', type=bounded_str, location='args')
    args = strict_parse_args(g.parser, request.args)

    results = filtering.events(
        namespace_id=g.namespace.id,
        event_public_id=args['event_id'],
        calendar_public_id=args['calendar_id'],
        title=args['title'],
        description=args['description'],
        location=args['location'],
        starts_before=args['starts_before'],
        starts_after=args['starts_after'],
        ends_before=args['ends_before'],
        ends_after=args['ends_after'],
        limit=args['limit'],
        offset=args['offset'],
        source='local',
        view=args['view'],
        db_session=g.db_session)

    return g.encoder.jsonify(results)


@app.route('/events/', methods=['POST'])
def event_create_api():
    # Handle ical uploads
    if request.headers.get('content-type') == 'text/calendar':
        ics_str = request.data
        new_events = events.crud.create_from_ics(g.namespace, g.db_session,
                                                 ics_str)
        if not new_events:
            return err(400, "Couldn't parse .ics file.")

        return g.encoder.jsonify(new_events)

    data = request.get_json(force=True)
    try:
        calendar = get_calendar(data.get('calendar_id'),
                                g.namespace, g.db_session)
    except InputError as e:
        return err(404, str(e))

    if calendar.read_only:
        return err(400, "Can't create events on read_only calendar.")

    try:
        valid_event(data)
    except InputError as e:
        return err(404, str(e))

    title = data.get('title', '')
    description = data.get('description')
    location = data.get('location')
    reminders = data.get('reminders')
    recurrence = data.get('recurrence')
    when = data.get('when')

    participants = data.get('participants', [])
    for p in participants:
        if 'status' not in p:
            p['status'] = 'noreply'

    new_event = events.crud.create(g.namespace, g.db_session,
                                     calendar,
                                     title,
                                     description,
                                     location,
                                     reminders,
                                     recurrence,
                                     when,
                                     participants)

    schedule_action('create_event', new_event, g.namespace.id, g.db_session)
    return g.encoder.jsonify(new_event)


@app.route('/events/<public_id>', methods=['GET'])
def event_read_api(public_id):
    """Get all data for an existing event."""
    try:
        valid_public_id(public_id)
    except InputError:
        return err(400, 'Invalid event id {}'.format(public_id))
    g.parser.add_argument('participant_id', type=valid_public_id,
                          location='args')
    g.parser.add_argument('action', type=valid_event_action, location='args')
    g.parser.add_argument('rsvp', type=valid_rsvp, location='args')
    args = strict_parse_args(g.parser, request.args)

    # FIXME karim -- re-enable this after landing the participants refactor (T687)
    #if 'action' in args:
    #    # Participants are able to RSVP to events by clicking on links (e.g.
    #    # that are emailed to them). Therefore, the RSVP action is invoked via
    #    # a GET.
    #    if args['action'] == 'rsvp':
    #        try:
    #            participant_id = args.get('participant_id')
    #            if not participant_id:
    #                return err(404, "Must specify a participant_id with rsvp")

    #            participant = g.db_session.query(Participant).filter_by(
    #                public_id=participant_id).one()

    #            participant.status = args['rsvp']
    #            g.db_session.commit()

    #            result = events.crud.read(g.namespace, g.db_session,
    #                                      public_id)

    #            if result is None:
    #                return err(404, "Couldn't find event with id {0}"
    #                           .format(public_id))

    #            return g.encoder.jsonify(result)
    #        except NoResultFound:
    #            return err(404, "Couldn't find participant with id `{0}` "
    #                       .format(participant_id))

    result = events.crud.read(g.namespace, g.db_session, public_id)
    if result is None:
        return err(404, "Couldn't find event with id {0}".
                   format(public_id))
    return g.encoder.jsonify(result)


@app.route('/events/<public_id>', methods=['PUT'])
def event_update_api(public_id):
    try:
        valid_public_id(public_id)
    except InputError:
        return err(400, 'Invalid event id {}'.format(public_id))
    data = request.get_json(force=True)

    try:
        valid_event_update(data, g.namespace, g.db_session)
    except InputError as e:
        return err(404, str(e))

    # Convert the data into our types where necessary
    # e.g. timestamps, participant_list
    if 'start' in data:
        data['start'] = datetime.utcfromtimestamp(int(data.get('start')))
    if 'end' in data:
        data['end'] = datetime.utcfromtimestamp(int(data.get('end')))
    if 'participants' in data:
        data['participant_list'] = []
        for p in data['participants']:
            if 'status' not in p:
                p['status'] = 'noreply'
            data['participant_list'].append(p)
        del data['participants']

    try:
        result = events.crud.update(g.namespace, g.db_session,
                                    public_id, data)
    except InputError as e:
        return err(400, str(e))

    if result is None:
        return err(404, "Couldn't find event with id {0}".
                   format(public_id))

    schedule_action('update_event', result, g.namespace.id, g.db_session)
    return g.encoder.jsonify(result)


@app.route('/events/<public_id>', methods=['DELETE'])
def event_delete_api(public_id):
    try:
        valid_public_id(public_id)
        event = g.db_session.query(Event).filter_by(
            public_id=public_id). \
            options(subqueryload(Event.calendar)).one()
    except InputError:
        return err(400, 'Invalid event id {}'.format(public_id))
    except NoResultFound:
        return err(404, 'No event found with public_id {}'.
                   format(public_id))
    if event.namespace != g.namespace:
        return err(404, 'No event found with public_id {}'.
                   format(public_id))
    if event.calendar.read_only:
        return err(404, 'Cannot delete event with public_id {} from '
                   ' read_only calendar.'.format(public_id))

    schedule_action('delete_event', event, g.namespace.id, g.db_session,
                    event_uid=event.uid,
                    calendar_name=event.calendar.name)
    events.crud.delete(g.namespace, g.db_session, public_id)
    return g.encoder.jsonify(None)


#
# Files
#
@app.route('/files/', methods=['GET'])
def files_api():
    g.parser.add_argument('filename', type=bounded_str, location='args')
    g.parser.add_argument('message_id', type=valid_public_id, location='args')
    g.parser.add_argument('file_id', type=valid_public_id, location='args')
    g.parser.add_argument('content_type', type=bounded_str, location='args')
    g.parser.add_argument('is_attachment', type=boolean, default=None,
                          location='args')
    g.parser.add_argument('view', type=view, location='args')

    args = strict_parse_args(g.parser, request.args)
    files = filtering.files(
        namespace_id=g.namespace.id,
        file_public_id=args['file_id'],
        message_public_id=args['message_id'],
        filename=args['filename'],
        content_type=args['content_type'],
        is_attachment=args['is_attachment'],
        limit=args['limit'],
        offset=args['offset'],
        view=args['view'],
        db_session=g.db_session)

    return g.encoder.jsonify(files)


@app.route('/files/<public_id>', methods=['GET'])
def file_read_api(public_id):
    try:
        valid_public_id(public_id)
        f = g.db_session.query(Block).filter(
            Block.public_id == public_id,
            Block.namespace_id == g.namespace.id).one()
        return g.encoder.jsonify(f)
    except InputError:
        return err(400, 'Invalid file id {}'.format(public_id))
    except NoResultFound:
        return err(404, "Couldn't find file with id {0} "
                   "on namespace {1}".format(public_id, g.namespace_public_id))


@app.route('/files/<public_id>', methods=['DELETE'])
def file_delete_api(public_id):
    try:
        valid_public_id(public_id)
        f = g.db_session.query(Block).filter(
            Block.public_id == public_id,
            Block.namespace_id == g.namespace.id).one()

        if g.db_session.query(Block).join(Part) \
                .filter(Block.public_id == public_id).first() is not None:
            return err(400, "Can't delete file that is attachment.")

        g.db_session.delete(f)
        g.db_session.commit()

        # This is essentially what our other API endpoints do after deleting.
        # Effectively no error == success
        return g.encoder.jsonify(None)
    except InputError:
        return err(400, 'Invalid file id {}'.format(public_id))
    except NoResultFound:
        return err(404, "Couldn't find file with id {0} "
                   "on namespace {1}".format(public_id, g.namespace_public_id))


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
    try:
        valid_public_id(public_id)
        f = g.db_session.query(Block).filter(
            Block.public_id == public_id,
            Block.namespace_id == g.namespace.id).one()
    except InputError:
        return err(400, 'Invalid file id {}'.format(public_id))
    except NoResultFound:
        return err(404, "Couldn't find file with id {0} "
                   "on namespace {1}".format(public_id, g.namespace_public_id))

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
    response.headers[
        'Content-Disposition'] = "attachment; filename={0}".format(name)
    g.log.info(response.headers)
    return response


##
# Calendars
##
@app.route('/calendars/', methods=['GET'])
def calendar_search_api():
    """ Calendar events! """
    g.parser.add_argument('filter', type=bounded_str, default='',
                          location='args')
    g.parser.add_argument('view', type=view, location='args')

    args = strict_parse_args(g.parser, request.args)
    term_filter_string = '%{}%'.format(args['filter'])
    term_filter = or_(
        Calendar.name.like(term_filter_string),
        Calendar.description.like(term_filter_string))

    eager = subqueryload(Calendar.events)

    if view == 'count':
        query = g.db_session(func.count(Calendar.id))
    elif view == 'ids':
        query = g.db_session.query(Calendar.id)
    else:
        query = g.db_session.query(Calendar)

    results = query.filter(Calendar.namespace_id == g.namespace.id,
                           term_filter).order_by(asc(Calendar.id))

    if view == 'count':
        return g.encoder.jsonify({"count": results.one()[0]})

    results = results.limit(args['limit'])

    if view != 'ids':
        results = results.options(eager)

    results = results.offset(args['offset']).all()

    return g.encoder.jsonify(results)


@app.route('/calendars/', methods=['POST'])
def calendar_create_api():
    data = request.get_json(force=True)

    if 'name' not in data:
        return err(404, "Calendar must have a name.")

    name = data['name']

    existing = g.db_session.query(Calendar).filter(
        Calendar.name == name,
        Calendar.namespace_id == g.namespace.id).first()

    if existing:
        return err(404, "Calendar already exists with name '{}'.".format(name))

    description = data.get('description', None)

    cal_create = events.crud.create_calendar
    new_calendar = cal_create(g.namespace, g.db_session, name, description)
    return g.encoder.jsonify(new_calendar)


@app.route('/calendars/<public_id>', methods=['GET'])
def calendar_read_api(public_id):
    """Get all data for an existing calendar."""
    try:
        valid_public_id(public_id)
    except InputError:
        return err(400, 'Invalid calendar id {}'.format(public_id))

    result = events.crud.read_calendar(g.namespace, g.db_session, public_id)
    if result is None:
        return err(404, "Couldn't find calendar with id {0}".
                   format(public_id))
    return g.encoder.jsonify(result)


@app.route('/calendars/<public_id>', methods=['PUT'])
def calendar_update_api(public_id):
    try:
        calendar = get_calendar(public_id, g.namespace, g.db_session)
    except InputError as e:
        return err(404, str(e))

    if calendar.read_only:
        return err(400, "Cannot update a read_only calendar.")

    data = request.get_json(force=True)
    result = events.crud.update_calendar(g.namespace, g.db_session,
                                         public_id, data)

    if result is None:
        return err(404, "Couldn't find calendar with id {0}".
                   format(public_id))
    return g.encoder.jsonify(result)


@app.route('/calendars/<public_id>', methods=['DELETE'])
def calendar_delete_api(public_id):
    try:
        calendar = get_calendar(public_id, g.namespace, g.db_session)
    except InputError as e:
        return err(404, str(e))

    if calendar.read_only:
        return err(400, "Cannot delete a read_only calendar.")

    result = events.crud.delete_calendar(g.namespace, g.db_session,
                                         public_id)

    return g.encoder.jsonify(result)


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
    g.parser.add_argument('thread_id', type=valid_public_id, location='args')
    g.parser.add_argument('tag', type=bounded_str, location='args')
    g.parser.add_argument('view', type=view, location='args')
    args = strict_parse_args(g.parser, request.args)
    drafts = filtering.drafts(
        namespace_id=g.namespace.id,
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
        tag=args['tag'],
        limit=args['limit'],
        offset=args['offset'],
        view=args['view'],
        db_session=g.db_session)

    return g.encoder.jsonify(drafts)


@app.route('/drafts/<public_id>', methods=['GET'])
def draft_get_api(public_id):
    try:
        valid_public_id(public_id)
    except InputError:
        return err(400, 'Invalid draft id {}'.format(public_id))
    draft = sendmail.get_draft(g.db_session, g.namespace.account, public_id)
    if draft is None:
        return err(404, 'No draft found with id {}'.format(public_id))
    return g.encoder.jsonify(draft)


@app.route('/drafts/', methods=['POST'])
def draft_create_api():
    data = request.get_json(force=True)

    to = get_recipients(data.get('to'), 'to')
    cc = get_recipients(data.get('cc'), 'cc')
    bcc = get_recipients(data.get('bcc'), 'bcc')
    subject = data.get('subject')
    body = data.get('body')
    try:
        tags = get_tags(data.get('tags'), g.namespace.id, g.db_session)
        files = get_attachments(data.get('file_ids'), g.namespace.id,
                                g.db_session)
        replyto_thread = get_thread(data.get('thread_id'),
                                    g.namespace.id, g.db_session)
    except InputError as e:
        return err(404, str(e))

    try:
        draft = sendmail.create_draft(g.db_session, g.namespace.account, to,
                                      subject, body, files, cc, bcc,
                                      tags, replyto_thread)
    except ActionError as e:
        return err(e.error, str(e))

    return g.encoder.jsonify(draft)


@app.route('/drafts/<public_id>', methods=['PUT'])
def draft_update_api(public_id):
    try:
        valid_public_id(public_id)
    except InputError:
        return err(400, 'Invalid draft id {}'.format(public_id))

    data = request.get_json(force=True)
    if data.get('version') is None:
        return err(400, 'Must specify version to update')

    version = data.get('version')
    original_draft = g.db_session.query(Message).filter(
        Message.public_id == public_id).first()
    if original_draft is None or not original_draft.is_draft or \
            original_draft.namespace.id != g.namespace.id:
        return err(404, 'No draft with public id {}'.format(public_id))
    if original_draft.version != version:
        return err(409, 'Draft {0}.{1} has already been updated to version '
                   '{2}'.format(public_id, version, original_draft.version))

    # TODO(emfree): what if you try to update a draft on a *thread* that's been
    # deleted?

    data = request.get_json(force=True)

    to = get_recipients(data.get('to'), 'to')
    cc = get_recipients(data.get('cc'), 'cc')
    bcc = get_recipients(data.get('bcc'), 'bcc')
    subject = data.get('subject')
    body = data.get('body')
    try:
        tags = get_tags(data.get('tags'), g.namespace.id, g.db_session)
        files = get_attachments(data.get('file_ids'), g.namespace.id,
                                g.db_session)
    except InputError as e:
        return err(404, str(e))

    try:
        draft = sendmail.update_draft(g.db_session, g.namespace.account,
                                      original_draft, to, subject, body,
                                      files, cc, bcc, tags)
    except ActionError as e:
        return err(e.error, str(e))

    return g.encoder.jsonify(draft)


@app.route('/drafts/<public_id>', methods=['DELETE'])
def draft_delete_api(public_id):
    data = request.get_json(force=True)
    if data.get('version') is None:
        return err(400, 'Must specify version to delete')
    version = data.get('version')

    try:
        valid_public_id(public_id)
        draft = g.db_session.query(Message).filter(
            Message.public_id == public_id).one()
    except InputError:
        return err(400, 'Invalid public id {}'.format(public_id))
    except NoResultFound:
        return err(404, 'No draft found with public_id {}'.
                   format(public_id))

    if draft.namespace != g.namespace:
        return err(404, 'No draft found with public_id {}'.
                   format(public_id))

    if not draft.is_draft:
        return err(400, 'Message with public id {} is not a draft'.
                   format(public_id))

    if draft.version != version:
        return err(409, 'Draft {0}.{1} has already been updated to version '
                   '{2}'.format(public_id, version, draft.version))

    try:
        result = sendmail.delete_draft(g.db_session, g.namespace.account,
                                       public_id)
    except ActionError as e:
        return err(e.error, str(e))

    return g.encoder.jsonify(result)


@app.route('/send', methods=['POST'])
def draft_send_api():
    if rate_limited(g.namespace.id, g.db_session):
        return err(429, 'Daily sending quota exceeded.')
    data = request.get_json(force=True)
    if data.get('draft_id') is None:
        if not data.get('to'):
            return err(400, 'Must specify either draft id + version or '
                       'message recipients.')
    else:
        if data.get('version') is None:
            return err(400, 'Must specify version to send')

    draft_public_id = data.get('draft_id')
    version = data.get('version')
    if draft_public_id is not None:
        try:
            valid_public_id(draft_public_id)
            draft = g.db_session.query(Message).filter(
                Message.public_id == draft_public_id).one()
        except InputError:
            return err(400, 'Invalid public id {}'.format(draft_public_id))
        except NoResultFound:
            return err(404, 'No draft found with id {}'.
                       format(draft_public_id))

        if draft.namespace != g.namespace:
            return err(404, 'No draft found with id {}'.
                       format(draft_public_id))

        if draft.is_sent or not draft.is_draft:
            return err(400, 'Message with id {} is not a draft'.
                       format(draft_public_id))

        if not draft.to_addr:
            return err(400, "No 'to:' recipients specified")

        if draft.version != version:
            return err(
                409, 'Draft {0}.{1} has already been updated to version {2}'.
                format(draft_public_id, version, draft.version))

        validate_draft_recipients(draft)

        try:
            schedule_action('send_draft', draft, g.namespace.id, g.db_session)
        except ActionError as e:
            return err(e.error, str(e))
    else:
        to = get_recipients(data.get('to'), 'to', validate_emails=True)
        cc = get_recipients(data.get('cc'), 'cc', validate_emails=True)
        bcc = get_recipients(data.get('bcc'), 'bcc', validate_emails=True)
        subject = data.get('subject')
        body = data.get('body')
        try:
            tags = get_tags(data.get('tags'), g.namespace.id, g.db_session)
            files = get_attachments(data.get('file_ids'), g.namespace.id,
                                    g.db_session)
            replyto_thread = get_thread(data.get('thread_id'),
                                        g.namespace.id, g.db_session)
        except InputError as e:
            return err(404, str(e))

        try:
            draft = sendmail.create_draft(g.db_session, g.namespace.account,
                                          to, subject, body, files, cc, bcc,
                                          tags, replyto_thread, syncback=False)
            schedule_action('send_directly', draft, g.namespace.id,
                            g.db_session)
        except ActionError as e:
            return err(e.error, str(e))

    draft.state = 'sending'
    return g.encoder.jsonify(draft)


##
# Client syncing
##

@app.route('/delta')
def sync_deltas():
    g.parser.add_argument('cursor', type=valid_public_id, location='args',
                          required=True)
    g.parser.add_argument('exclude_types', type=valid_delta_object_types,
                          location='args')
    args = strict_parse_args(g.parser, request.args)
    cursor = args['cursor']
    if cursor == '0':
        start_pointer = 0
    else:
        try:
            start_pointer, = g.db_session.query(Transaction.id). \
                filter(Transaction.public_id == cursor,
                       Transaction.namespace_id == g.namespace.id).one()
        except NoResultFound:
            return err(404, 'Invalid cursor parameter')
    exclude_types = args.get('exclude_types')
    deltas, _ = delta_sync.format_transactions_after_pointer(
        g.namespace.id, start_pointer, g.db_session, args['limit'],
        delta_sync._format_transaction_for_delta_sync, exclude_types)
    response = {
        'cursor_start': cursor,
        'deltas': deltas,
    }
    if deltas:
        response['cursor_end'] = deltas[-1]['cursor']
    else:
        # No changes.
        response['cursor_end'] = cursor
    return g.encoder.jsonify(response)


@app.route('/delta/generate_cursor', methods=['POST'])
def generate_cursor():
    data = request.get_json(force=True)
    if data.keys() != ['start'] or not isinstance(data['start'], int):
        return err(400, 'generate_cursor request body must have the format '
                        '{"start": <Unix timestamp>}')

    timestamp = int(data['start'])
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
    args = strict_parse_args(g.parser, request.args)
    timeout = args['timeout'] or 3600
    transaction_pointer = None
    cursor = args['cursor']
    if cursor == '0':
        transaction_pointer = 0
    else:
        query_result = g.db_session.query(Transaction.id).filter(
            Transaction.namespace_id == g.namespace.id,
            Transaction.public_id == cursor).first()
        if query_result is None:
            return err(400, 'Invalid cursor {}'.format(args['cursor']))
        transaction_pointer = query_result[0]
    exclude_types = args.get('exclude_types')

    # Hack to not keep a database session open for the entire (long) request
    # duration.
    g.db_session.close()
    generator = delta_sync.streaming_change_generator(
        g.namespace.id, transaction_pointer=transaction_pointer,
        poll_interval=1, timeout=timeout, exclude_types=exclude_types)
    return Response(generator, mimetype='text/event-stream')
