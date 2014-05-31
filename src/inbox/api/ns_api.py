import os

import zerorpc
from flask import request, g, Blueprint, make_response, current_app, Response
from flask import jsonify as flask_jsonify
from sqlalchemy import asc
from sqlalchemy.orm.exc import NoResultFound
from werkzeug.exceptions import default_exceptions
from werkzeug.exceptions import HTTPException

from inbox.server.models.tables.base import (
    Message, Block, Part, Thread, Namespace, Lens, Webhook, UserTag, Contact)
from inbox.server.models.kellogs import jsonify
from inbox.server.config import config
from inbox.server import contacts
from inbox.server.models import InboxSession, session_scope
from inbox.server import sendmail

from err import err


DEFAULT_LIMIT = 50
SPECIAL_LABELS = [
    'inbox',
    'all',
    'archive',
    'drafts'
    'sent',
    'spam',
    'starred',
    'trash',
    'attachment']


app = Blueprint(
    'namespace_api',
    __name__,
    url_prefix='/n/<namespace_public_id>')

# Configure mimietype -> extension map
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


@app.record
def record_auth(setup_state):
    # Runs when the Blueprint binds to the main application
    main_app = setup_state.app

    @main_app.route('/n/')
    def ns_all():
        """ Return all namespaces """
        # We do this outside the blueprint to support the case of an empty public_id.
        # However, this means the before_request isn't run, so we need to make our own session
        with session_scope() as db_session:
            namespaces = db_session.query(Namespace).all()
            result = jsonify(namespaces)
        return result


@app.before_request
def start():
    g.db_session = InboxSession()

    g.log = current_app.logger
    try:
        g.namespace = g.db_session.query(Namespace) \
            .filter(Namespace.public_id == g.namespace_public_id).one()
    except NoResultFound:
        return err(404, "Couldn't find namespace with id `{0}` ".format(
            g.namespace_public_id))

    try:
        g.lens = Lens(
            namespace_id=g.namespace.id,
            subject=request.args.get('subject'),
            thread_public_id=request.args.get('thread'),
            to_addr=request.args.get('to'),
            from_addr=request.args.get('from'),
            cc_addr=request.args.get('cc'),
            bcc_addr=request.args.get('bcc'),
            any_email=request.args.get('any_email'),
            started_before=request.args.get('started_before'),
            started_after=request.args.get('started_after'),
            last_message_before=request.args.get('last_message_before'),
            last_message_after=request.args.get('last_message_after'),
            filename=request.args.get('filename'),
            tag=request.args.get('tag'),
            detached=True)
        g.lens_limit = request.args.get('limit')
        g.lens_offset = request.args.get('offset')
    except ValueError as e:
        return err(400, e.message)


@app.after_request
def finish(response):
    if response.status_code == 200:
        g.db_session.commit()
    g.db_session.close()
    return response


@app.record
def record_auth(setup_state):
    # Runs when the Blueprint binds to the main application
    app = setup_state.app

    def default_json_error(ex):
        """ Exception -> flask JSON responder """
        app.logger.error("Uncaught error thrown by Flask/Werkzeug: {0}"
                         .format(ex))
        response = flask_jsonify(message=str(ex), type='api_error')
        response.status_code = (ex.code
                                if isinstance(ex, HTTPException)
                                else 500)
        return response

    # Patch all error handlers in werkzeug
    for code in default_exceptions.iterkeys():
        app.error_handler_spec[None][code] = default_json_error


@app.errorhandler(NotImplementedError)
def handle_not_implemented_error(error):
    response = flask_jsonify(message="API endpoint not yet implemented.",
                             type='api_error')
    response.status_code = 501
    return response


#
# General namespace info
#
@app.route('/')
def index():
    return jsonify(g.namespace)


##
# Tags
##
@app.route('/tags')
def tag_query_api():
    results = list(g.namespace.usertags.union(g.namespace.account.folders))
    return jsonify(results)


@app.route('/tags', methods=['POST'])
def tag_create_api():
    data = request.get_json(force=True)
    if data.keys() != ['name']:
        return err(400, 'Malformed tag request')
    tag_name = data['name']
    if not UserTag.name_available(tag_name, g.namespace.id, g.db_session):
        return err(409, 'Tag name not available')

    tag = UserTag(name=tag_name, namespace=g.namespace)
    g.db_session.commit()
    return jsonify(tag)


#
# Threads
#
@app.route('/threads')
def thread_query_api():
    return jsonify(g.lens.thread_query(g.db_session, limit=g.lens_limit,
                                       offset=g.lens_offset).all())


@app.route('/threads/<public_id>')
def thread_api(public_id):
    public_id = public_id.lower()
    try:
        thread = g.db_session.query(Thread).filter(
            Thread.public_id == public_id,
            Thread.namespace_id == g.namespace.id).one()
        return jsonify(thread)

    except NoResultFound:
        return err(404, "Couldn't find thread with id `{0}` "
                   "on namespace {1}".format(public_id, g.namespace_public_id))


#
# Update thread
#
@app.route('/threads/<public_id>', methods=['PUT'])
def thread_api_update(public_id):
    try:
        thread = g.db_session.query(Thread).filter(
            Thread.public_id == public_id,
            Thread.namespace_id == g.namespace.id).one()
    except NoResultFound:
        return err(404, "Couldn't find thread with id `{0}` "
                   "on namespace {1}".format(public_id, g.namespace_public_id))
    data = request.get_json(force=True)
    if not set(data).issubset({'add_tags', 'remove_tags'}):
        return err(400, 'Can only add or remove tags from thread.')

    removals = data.get('remove_tags', [])

    # TODO(emfree) Currently trying to add/remove a read-only tag (i.e.,
    # anything but a UserTag) will give a "no tag found" error.

    for tag_name in removals:
        try:
            tag = g.db_session.query(UserTag).filter(
                UserTag.namespace_id == g.namespace.id,
                UserTag.name == tag_name).one()
            thread.usertags.discard(tag)
        except NoResultFound:
            return err(404, 'No tag found with name {}'.  format(tag_name))

    additions = data.get('add_tags', [])
    for tag_name in additions:
        try:
            tag = g.db_session.query(UserTag).filter(
                UserTag.namespace_id == g.namespace.id,
                UserTag.name == tag_name).one()
            thread.usertags.add(tag)
        except NoResultFound:
            return err(404, 'No tag found with name {}'.  format(tag_name))

    g.db_session.commit()
    return jsonify(thread)


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
@app.route('/messages')
def message_query_api():
    return jsonify(g.lens.message_query(g.db_session, limit=g.lens_limit,
                                        offset=g.lens_offset).all())


@app.route('/messages/<public_id>')
def message_api(public_id):
    if public_id == 'all':
        # TODO assert limit query parameter

        all_messages = g.db_session.query(Message).join(Thread).filter(
            Thread.namespace_id == g.namespace.id).limit(DEFAULT_LIMIT).all()
        return jsonify(all_messages)

    try:
        m = g.db_session.query(Message).filter(
            Message.public_id == public_id).one()
        assert int(m.namespace.id) == int(g.namespace.id)
        return jsonify(m)

    except NoResultFound:
        return err(404,
                   "Couldn't find message with id {0} "
                   "on namespace {1}".format(public_id, g.namespace_public_id))


#
# Contacts
##
@app.route('/contacts', methods=['GET'])
def contact_search_api():
    filter = request.args.get('filter', '')
    try:
        limit = int(request.args.get('limit', 10))
        offset = int(request.args.get('offset', 0))
    except ValueError:
        return err(400, 'limit and offset parameters must be integers')
    if limit < 0 or offset < 0:
        return err(400, 'limit and offset parameters must be nonnegative '
                        'integers')
    if limit > 1000:
        return err(400, 'cannot request more than 1000 contacts at once.')
    order = request.args.get('order')
    if order == 'rank':
        results = contacts.search_util.search(g.db_session,
                                              g.namespace.account_id, filter,
                                              limit, offset)
    else:
        results = g.db_session.query(Contact). \
            filter(Contact.account_id == g.namespace.account_id,
                   Contact.source == 'local'). \
            order_by(asc(Contact.id)).limit(limit).offset(offset).all()

    return jsonify(results)


@app.route('/contacts', methods=['POST'])
def contact_create_api():
    # TODO(emfree) Detect attempts at duplicate insertions.
    data = request.get_json(force=True)
    name = data.get('name')
    email = data.get('email')
    if not any((name, email)):
        return err(400, 'Contact name and email cannot both be null.')
    new_contact = contacts.crud.create(g.namespace, g.db_session,
                                       name, email)
    return jsonify(new_contact)


@app.route('/contacts/<public_id>', methods=['GET'])
def contact_read_api(public_id):
    # TODO auth with account object
    # Get all data for an existing contact.
    result = contacts.crud.read(g.namespace, g.db_session, public_id)
    if result is None:
        return err(404, "Couldn't find contact with id {0}".
                   format(public_id))
    return jsonify(result)


@app.route('/contacts/<public_id>', methods=['PUT'])
def contact_update_api(public_id):
    raise NotImplementedError


@app.route('/contacts/<public_id>', methods=['DELETE'])
def contact_delete_api(public_id):
    raise NotImplementedError


#
# Files
#
@app.route('/files/<public_id>')
def files_api(public_id):
    if public_id == 'all':
        # TODO assert limit query parameter
        # TODO perhaps return just if content_disposition == 'attachment'
        all_files = g.db_session.query(Part) \
            .filter(Part.namespace_id == g.namespace.id) \
            .filter(Part.content_disposition is not None) \
            .limit(DEFAULT_LIMIT).all()
        return jsonify(all_files)

    try:
        f = g.db_session.query(Block).filter(
            Block.public_id == public_id).one()
        assert int(f.message.namespace.id) == int(g.namespace.id)
        return jsonify(f)

    except NoResultFound:
        return err(404, "Couldn't find file with id {0} "
                   "on namespace {1}".format(public_id, g.namespace_public_id))


#
# Upload file
#
@app.route('/files/upload', methods=['POST'])
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
    return jsonify(all_files)


#
# File downloads
#
@app.route('/files/<public_id>/download')
def file_download_api(public_id):

    try:
        f = g.db_session.query(Block).filter(
            Block.public_id == public_id).one()
        assert int(f.namespace_id) == int(g.namespace.id)
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


@app.route('/webhooks', methods=['GET'])
def webhooks_read_all_api():
    return jsonify(g.db_session.query(Webhook).
                   filter(Webhook.namespace_id == g.namespace_id).all())


@app.route('/webhooks', methods=['POST'])
def webhooks_create_api():
    try:
        parameters = request.get_json(force=True)
        result = get_webhook_client().register_hook(g.namespace.id, parameters)
        return Response(result, mimetype='application/json')
    except zerorpc.RemoteError:
        return err(400, 'Malformed webhook request')


@app.route('/webhooks/<public_id>', methods=['GET', 'PUT'])
def webhooks_read_update_api(public_id):
    if request.method == 'GET':
        try:
            hook = g.db_session.query(Webhook).filter(
                Webhook.public_id == public_id,
                Webhook.namespace_id == g.namespace.id).one()
            return jsonify(hook)
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
            return jsonify({"success": True})
        except zerorpc.RemoteError:
            return err(404, "Couldn't find webhook with id {}"
                       .format(public_id))


@app.route('/webhooks/<public_id>', methods=['DELETE'])
def webhooks_delete_api(public_id):
    raise NotImplementedError


##
# Drafts
##
@app.route('/drafts', methods=['GET'])
def draft_get_all_api():
    drafts = sendmail.get_all_drafts(g.db_session, g.namespace.account)
    return jsonify(drafts)


@app.route('/drafts/<public_id>', methods=['GET'])
def draft_get_api(public_id):
    draft = sendmail.get_draft(g.db_session, g.namespace.account, public_id)
    return jsonify(draft)


@app.route('/drafts', methods=['POST'])
def draft_create_api():
    try:
        data = request.get_json(force=True)
    except ValueError:
        return err(400, 'Malformed request')

    to = data.get('to')
    cc = data.get('cc')
    bcc = data.get('bcc')
    subject = data.get('subject')
    body = data.get('body')
    files = data.get('files')

    thread_public_id = data.get('reply_to_thread')

    draft = sendmail.create_draft(g.db_session, g.namespace.account, to,
                                  subject, body, files, cc, bcc,
                                  thread_public_id)

    return jsonify(draft)


@app.route('/drafts/<public_id>', methods=['POST'])
def draft_update_api(public_id):
    try:
        data = request.get_json(force=True)
    except ValueError:
        return err(400, 'Malformed request')

    to = data.get('to')
    cc = data.get('cc')
    bcc = data.get('bcc')
    subject = data.get('subject')
    body = data.get('body')
    files = data.get('files')

    draft = sendmail.update_draft(g.db_session, g.namespace.account, public_id,
                                  to, subject, body, files, cc, bcc)

    return jsonify(draft)


@app.route('/drafts/<public_id>', methods=['DELETE'])
def draft_delete_api(public_id):
    result = sendmail.delete_draft(g.db_session, g.namespace.account,
                                   public_id)
    return jsonify(result)


@app.route('/send', methods=['POST'])
def draft_send_api():
    try:
        data = request.get_json(force=True)
    except ValueError:
        return err(400, 'Malformed request')

    draft_public_id = data.get('draft_id')

    to = data.get('to')
    cc = data.get('cc')
    bcc = data.get('bcc')
    subject = data.get('subject')
    body = data.get('body')
    files = data.get('files')

    if not draft_public_id or to:
        return err(400, 'Malformed request')

    result = sendmail.send_draft(g.db_session, g.namespace.account,
                                 draft_public_id, to, subject, body, files,
                                 cc, bcc)
    return jsonify(result)
