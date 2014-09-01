import os

import zerorpc
from datetime import datetime
from flask import request, g, Blueprint, make_response, Response
from flask import jsonify as flask_jsonify
from flask.ext.restful import reqparse
from sqlalchemy import asc, or_
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm import subqueryload

from inbox.models import (Message, Block, Thread, Namespace, Webhook,
                          Tag, Contact, Event, Participant)
from inbox.api.kellogs import APIEncoder
from inbox.api import filtering
from inbox.api.validation import (InputError, get_tags, get_attachments,
                                  get_thread, valid_public_id, valid_event,
                                  valid_event_update, timestamp, bounded_str,
                                  strict_parse_args, limit, valid_event_action,
                                  valid_rsvp, ValidatableArgument)
from inbox.config import config
from inbox import events, contacts, sendmail
from inbox.log import get_logger
from inbox.models.constants import MAX_INDEXABLE_LENGTH
from inbox.models.action_log import schedule_action
from inbox.models.session import InboxSession
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
    results = list(g.namespace.tags.values())
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
    if 'name' not in data.keys():
        return err(400, 'Malformed tag update request')
    if 'namespace_id' in data.keys():
        ns_id = data['namespace_id']
        valid_public_id(ns_id)
        if ns_id != g.namespace.id:
            return err(400, 'Cannot change the namespace on a tag.')
    if not tag.user_created:
        return err(403, 'Cannot modify tag {}'.format(public_id))
    new_name = data['name']

    if new_name != tag.name:  # short-circuit rename to same value
        if not Tag.name_available(new_name, g.namespace.id, g.db_session):
            return err(409, 'Tag name already used')
        tag.name = new_name
        g.db_session.commit()
    # TODO(emfree) also support deleting user-created tags.

    return g.encoder.jsonify(tag)


@app.route('/tags/', methods=['POST'])
def tag_create_api():
    data = request.get_json(force=True)
    if 'name' not in data.keys():
        return err(400, 'Malformed tag request')
    if 'namespace_id' in data.keys():
        ns_id = data['namespace_id']
        valid_public_id(ns_id)
        if ns_id != g.namespace.id:
            return err(400, 'Cannot change the namespace on a tag.')
    tag_name = data['name']
    if not Tag.name_available(tag_name, g.namespace.id, g.db_session):
        return err(409, 'Tag name not available')
    if len(tag_name) > MAX_INDEXABLE_LENGTH:
        return err(400, 'Tag name is too long.')

    tag = Tag(name=tag_name, namespace=g.namespace, user_created=True)
    g.db_session.commit()
    return g.encoder.jsonify(tag)


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
        db_session=g.db_session)

    return g.encoder.jsonify(threads)


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
        return err(400, 'Invalid draft id {}'.format(public_id))
    except NoResultFound:
        return err(404, "Couldn't find thread with id `{0}` "
                   "on namespace {1}".format(public_id, g.namespace_public_id))
    data = request.get_json(force=True)
    if not set(data).issubset({'add_tags', 'remove_tags'}):
        return err(400, 'Can only add or remove tags from thread.')

    removals = data.get('remove_tags', [])

    # TODO(emfree) possibly also support adding/removing tags by tag public id,
    # not just name.

    for tag_name in removals:
        tag = g.db_session.query(Tag).filter(
            Tag.namespace_id == g.namespace.id,
            Tag.name == tag_name).first()
        if tag is None:
            return err(404, 'No tag found with name {}'.  format(tag_name))
        if not tag.user_removable:
            return err(400, 'Cannot remove tag {}'.format(tag_name))
        thread.remove_tag(tag, execute_action=True)

    additions = data.get('add_tags', [])
    for tag_name in additions:
        tag = g.db_session.query(Tag).filter(
            Tag.namespace_id == g.namespace.id,
            Tag.name == tag_name).first()
        if tag is None:
            return err(404, 'No tag found with name {}'.format(tag_name))
        if not tag.user_addable:
            return err(400, 'Cannot add tag {}'.format(tag_name))
        thread.apply_tag(tag, execute_action=True)

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
        db_session=g.db_session)

    return g.encoder.jsonify(messages)


@app.route('/messages/<public_id>', methods=['GET', 'PUT'])
def message_api(public_id):
    try:
        valid_public_id(public_id)
        message = g.db_session.query(Message).filter(
            Message.public_id == public_id).one()
        assert int(message.namespace.id) == int(g.namespace.id)
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


#
# Contacts
##
@app.route('/contacts/', methods=['GET'])
def contact_search_api():
    g.parser.add_argument('filter', type=bounded_str, default='',
                          location='args')
    args = strict_parse_args(g.parser, request.args)
    term_filter_string = '%{}%'.format(args['filter'])
    term_filter = or_(
        Contact.name.like(term_filter_string),
        Contact.email_address.like(term_filter_string))
    results = g.db_session.query(Contact). \
        filter(Contact.account_id == g.namespace.account_id,
               Contact.source == 'local',
               term_filter). \
        order_by(asc(Contact.id)).limit(args['limit']). \
        offset(args['offset']).all()

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


#
# Events
##
@app.route('/events/', methods=['GET'])
def event_search_api():
    g.parser.add_argument('filter', type=str, default='', location='args')
    args = strict_parse_args(g.parser, request.args)
    results = g.db_session.query(Event). \
        filter(Event.account_id == g.namespace.account_id,
               Event.source == 'local'). \
        order_by(asc(Event.id)).limit(args['limit']). \
        options(subqueryload(Event.participants_by_email)). \
        offset(args['offset']).all()

    return g.encoder.jsonify(results)


@app.route('/events/', methods=['POST'])
def event_create_api():
    # Handle ical uploads
    if request.headers['content-type'] == 'text/calendar':
        ics_str = request.data
        new_events = events.crud.create_from_ics(g.namespace, g.db_session,
                                                 ics_str)
        if not new_events:
            return err(400, "Couldn't parse .ics file.")

        return g.encoder.jsonify(new_events)

    data = request.get_json(force=True)

    try:
        valid_event(data)
    except InputError as e:
        return err(404, e.message)

    subject = data.get('subject', '')
    body = data.get('body')
    location = data.get('location')
    reminders = data.get('reminders')
    recurrence = data.get('recurrence')
    when = data.get('when')

    participants = data.get('participants', [])
    for p in participants:
        if 'status' not in p:
            p['status'] = 'noreply'

    new_contact = events.crud.create(g.namespace, g.db_session,
                                     subject,
                                     body,
                                     location,
                                     reminders,
                                     recurrence,
                                     when,
                                     participants)
    return g.encoder.jsonify(new_contact)


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

    if 'action' in args:
        # Participants are able to RSVP to events by clicking on links (e.g.
        # that are emailed to them). Therefore, the RSVP action is invoked via
        # a GET.
        if args['action'] == 'rsvp':
            try:
                participant_id = args.get('participant_id')
                if not participant_id:
                    return err(404, "Must specify a participant_id with rsvp")

                participant = g.db_session.query(Participant).filter_by(
                    public_id=participant_id).one()

                participant.status = args['rsvp']
                g.db_session.commit()

                result = events.crud.read(g.namespace, g.db_session,
                                          public_id)

                if result is None:
                    return err(404, "Couldn't find event with id {0}"
                               .format(public_id))

                return g.encoder.jsonify(result)
            except NoResultFound:
                return err(404, "Couldn't find participant with id `{0}` "
                           .format(participant_id))

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
        valid_event_update(data)
    except InputError as e:
        return err(404, e.message)

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
        return err(404, e.message)

    if result is None:
        return err(404, "Couldn't find event with id {0}".
                   format(public_id))
    return g.encoder.jsonify(result)


@app.route('/events/<public_id>', methods=['DELETE'])
def event_delete_api(public_id):
    try:
        valid_public_id(public_id)
        event = g.db_session.query(Event).filter_by(
            public_id=public_id).one()
    except InputError:
        return err(400, 'Invalid event id {}'.format(public_id))
    except NoResultFound:
        return err(404, 'No event found with public_id {}'.
                   format(public_id))
    if event.namespace != g.namespace:
        return err(404, 'No event found with public_id {}'.
                   format(public_id))
    if event.provider_name != 'inbox':
        return err(404, 'Cannot delete provider-based event with public_id {}'.
                        format(public_id))

    result = events.crud.delete(g.namespace, g.db_session, public_id)
    return g.encoder.jsonify(result)


#
# Files
#
@app.route('/files/', methods=['GET'])
def files_api():
    # TODO perhaps return just if content_disposition == 'attachment'
    g.parser.add_argument('filename', type=bounded_str, location='args')
    g.parser.add_argument('message', type=valid_public_id, location='args')
    args = strict_parse_args(g.parser, request.args)
    files = filtering.files(
        namespace_id=g.namespace.id,
        message_public_id=args['message'],
        filename=args['filename'],
        limit=args['limit'],
        offset=args['offset'],
        db_session=g.db_session)

    return g.encoder.jsonify(files)


@app.route('/files/<public_id>')
def file_read_api(public_id):
    try:
        valid_public_id(public_id)
        f = g.db_session.query(Block).filter(
            Block.public_id == public_id).one()
        if hasattr(f, 'message'):
            assert int(f.message.namespace.id) == int(g.namespace.id)
            g.log.info(
                "block's message namespace matches api context namespace")
        else:
            # Block was likely uploaded via file API and not yet sent in a msg
            g.log.debug("This block doesn't have a corresponding message: {}"
                        .format(f.public_id))
        return g.encoder.jsonify(f)
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
            Block.public_id == public_id).one()
        assert int(f.namespace_id) == int(g.namespace.id)
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
# Calendar
##
@app.route('/events/<public_id>')
def events_api(public_id):
    """ Calendar events! """
    raise NotImplementedError


##
# Webhooks
##
def get_webhook_client():
    if not hasattr(g, 'webhook_client'):
        g.webhook_client = zerorpc.Client()
        g.webhook_client.connect(config.get('WEBHOOK_SERVER_LOC'))
    return g.webhook_client


@app.route('/webhooks/', methods=['GET'])
def webhooks_read_all_api():
    return g.encoder.jsonify(g.db_session.query(Webhook).filter(
        Webhook.namespace_id == g.namespace.id).all())


@app.route('/webhooks/', methods=['POST'])
def webhooks_create_api():
    try:
        parameters = request.get_json(force=True)
        result = get_webhook_client().register_hook(g.namespace.id, parameters)
        return Response(result, mimetype='application/json')
    except zerorpc.RemoteError:
        return err(400, 'Malformed webhook request')


@app.route('/webhooks/<public_id>', methods=['GET', 'PUT'])
def webhooks_read_update_api(public_id):
    try:
        valid_public_id(public_id)
    except InputError:
        return err(400, 'Invalid webhook id {}'.format(public_id))
    if request.method == 'GET':
        try:
            hook = g.db_session.query(Webhook).filter(
                Webhook.public_id == public_id,
                Webhook.namespace_id == g.namespace.id).one()
            return g.encoder.jsonify(hook)
        except NoResultFound:
            return err(404, "Couldn't find webhook with id {}"
                       .format(public_id))

    if request.method == 'PUT':
        data = request.get_json(force=True)
        # We only support updates to the 'active' flag.
        if data.keys() != ['active']:
            return err(400, 'Malformed webhook request')

        try:
            if data['active']:
                get_webhook_client().start_hook(public_id)
            else:
                get_webhook_client().stop_hook(public_id)
            return g.encoder.jsonify({"success": True})
        except zerorpc.RemoteError:
            return err(404, "Couldn't find webhook with id {}"
                       .format(public_id))


@app.route('/webhooks/<public_id>', methods=['DELETE'])
def webhooks_delete_api(public_id):
    raise NotImplementedError


##
# Drafts
##

# TODO(emfree, kavya): Systematically validate user input, and return
# meaningful errors for invalid input.

@app.route('/drafts/')
def draft_query_api():
    g.parser.add_argument('thread_id', type=valid_public_id,
                          location='args')
    args = strict_parse_args(g.parser, request.args)
    drafts = filtering.drafts(g.namespace.id, args['thread_id'], args['limit'],
                              args['offset'], g.db_session)
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

    to = data.get('to')
    cc = data.get('cc')
    bcc = data.get('bcc')
    subject = data.get('subject')
    body = data.get('body')
    try:
        tags = get_tags(data.get('tags'), g.namespace.id, g.db_session)
        files = get_attachments(data.get('file_ids'), g.namespace.id,
                                g.db_session)
        replyto_thread = get_thread(data.get('thread_id'),
                                    g.namespace.id, g.db_session)
    except InputError as e:
        return err(404, e.message)

    draft = sendmail.create_draft(g.db_session, g.namespace.account, to,
                                  subject, body, files, cc, bcc,
                                  tags, replyto_thread)

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

    to = data.get('to')
    cc = data.get('cc')
    bcc = data.get('bcc')
    subject = data.get('subject')
    body = data.get('body')
    try:
        tags = get_tags(data.get('tags'), g.namespace.id, g.db_session)
        files = get_attachments(data.get('file_ids'), g.namespace.id,
                                g.db_session)
    except InputError as e:
        return err(404, e.message)

    draft = sendmail.update_draft(g.db_session, g.namespace.account,
                                  original_draft, to, subject, body,
                                  files, cc, bcc, tags)
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

    result = sendmail.delete_draft(g.db_session, g.namespace.account,
                                   public_id)
    return g.encoder.jsonify(result)


@app.route('/send', methods=['POST'])
def draft_send_api():
    data = request.get_json(force=True)
    if data.get('draft_id') is None:
        if data.get('to') is None:
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

        schedule_action('send_draft', draft, g.namespace.id, g.db_session)
    else:
        to = data.get('to')
        cc = data.get('cc')
        bcc = data.get('bcc')
        subject = data.get('subject')
        body = data.get('body')
        try:
            tags = get_tags(data.get('tags'), g.namespace.id, g.db_session)
            files = get_attachments(data.get('file_ids'), g.namespace.id,
                                    g.db_session)
            replyto_thread = get_thread(data.get('thread_id'),
                                        g.namespace.id, g.db_session)
        except InputError as e:
            return err(404, e.message)

        draft = sendmail.create_draft(g.db_session, g.namespace.account, to,
                                      subject, body, files, cc, bcc,
                                      tags, replyto_thread, syncback=False)
        schedule_action('send_directly', draft, g.namespace.id, g.db_session)

    draft.state = 'sending'
    return g.encoder.jsonify(draft)


##
# Client syncing
##

@app.route('/delta')
def sync_deltas():
    g.parser.add_argument('cursor', type=valid_public_id, location='args',
                          required=True)
    args = strict_parse_args(g.parser, request.args)
    try:
        results = delta_sync.get_entries_from_public_id(
            g.namespace.id, args['cursor'], g.db_session, args['limit'])
        return g.encoder.jsonify(results)
    except ValueError:
        return err(404, 'Invalid cursor parameter')


@app.route('/delta/generate_cursor', methods=['POST'])
def generate_cursor():
    data = request.get_json(force=True)
    if data.keys() != ['start'] or not isinstance(data['start'], int):
        return err(400, 'generate_cursor request body must have the format '
                        '{"start": <Unix timestamp>}')

    timestamp = int(data['start'])
    cursor = delta_sync.get_public_id_from_ts(g.namespace.id, timestamp,
                                              g.db_session)
    return g.encoder.jsonify({'cursor': cursor})
