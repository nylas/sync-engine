import os
import json

from flask import request, g, Blueprint, make_response, current_app, Response
import zerorpc

from sqlalchemy.orm.exc import NoResultFound

from inbox.server.models.tables.base import (
    Message, Block, Part, Contact, Thread, Namespace, Lens, Webhook)
from inbox.server.models.kellogs import jsonify
from inbox.server.config import config
from inbox.server import contacts

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


@app.before_request
def start():
    g.log = current_app.logger
    # TODO implement namespace + auth token check
    g.log.error("Havent implemented namespace auth!")

    # user = db_session.query(User).join(Account)\
    #     .filter(Account.id == g.user_id).one()
    # for account in user.accounts:
    #     account_ns = account.namespace
    #     private_ns.append(account_ns)
    # g.namespaces = private_ns

    try:
        g.namespace = g.db_session.query(Namespace) \
            .filter(Namespace.public_id == g.namespace_public_id).one()
    except NoResultFound:
        return err(404, "Couldn't find namespace {}".
                   format(g.namespace_public_id))

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
        detached=True)
    g.lens_limit = request.args.get('limit')
    g.lens_offset = request.args.get('offset')


##
# General namespace info
##
@app.route('')
def index():
    return jsonify(g.namespace)


##
# Folders/labels TODO
##
@app.route('/labels/<public_id>')
def folder_api(public_id):

    if public_id.lower() in SPECIAL_LABELS:
        pass  # TODO handle here
        raise NotImplementedError

    # else, we fetch it using the label table/object
    # TODO add full CRUD
    raise NotImplementedError


##
# Threads
##
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


# Update thread, ie: change labels/flags
# curl -u secret_key_234uoihlnsfkjansdf:  \
# http://192.168.10.200:5555/n/1/threads/cr0va02sv28nxqrvrvyjlhfeh \
# -X PUT \
# -H 'Content-Type: application/json' \
# -d '{"lables":"archive"}'
##
@app.route('/threads/<public_id>', methods=['PUT'])
def thread_api_update(public_id):

    # force ignores the Content-Type header, which really should
    # be set as application/json
    j = request.get_json(force=True, silent=True)
    if j is None:
        return err(409, "Badly formed JSON for a thread object. "
                   "For more details about modifying threads, see "
                   "https://www.inboxapp.com/docs#threads")

    raise NotImplementedError
    # TODO verify JSON objects to update thread.
    # Only thing that can change is labels
    # return jsonify(j)  # TODO don't just echo


#
#  Delete mail
#
# XXX TODO register a failure handler that reverses the local state
# change if the change fails to go through---this could cause our
# repository to get out of sync with the remote if another client
# does the same change in the meantime and we apply that change and
# *then* the change reversal goes through... but we can make this
# eventually consistent by doing a full comparison once a day or
# something.
@app.route('/threads/<public_id>', methods=['DELETE'])
def thread_api_delete(public_id):
    """ Moves the thread to the trash """
    raise NotImplementedError


#
#  Convienence methods for changing the labels on a thread
#
@app.route('/threads/<public_id>/<operation>')
def thread_operation_api(public_id, operation):
    operation = operation.lower()

    thread = g.db_session.query(Thread).filter(
        Thread.public_id == public_id,
        Thread.namespace_id == g.namespace.id).one()

    if not int(thread.namespace.id) == int(g.namespace.id):
        return err(410, "No access")  # todo better error


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


##
# Contacts
##
@app.route('/contacts', methods=['GET'])
def contact_search_api():
    filter = request.args.get('filter', '')
    limit = request.args.get('limit', 10)
    # TODO(emfree) support offset as well
    results = contacts.search_util.search(g.db_session, g.namespace.account_id,
                                          filter, limit)
    return jsonify(results)


@app.route('/contacts', methods=['POST'])
def contact_create_api():
    # TODO(emfree) Detect attempts at duplicate insertions.
    try:
        data = json.loads(request.data)
    except ValueError:
        return err(400, 'Malformed contact request')
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


##
# Files
##
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
# Download file
# consider hosting this behind a separate url like
# https://www.inboxusercontent.com/d/9y8734rhoirlkwqbfq
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
# Send
#
@app.route('/send', methods=['POST'])
def send_api():
    # TODO
    # Verify all attachments have been uploaded
    # from inbox.server.sendmail.base import send
    pass

    """ Send a new message. Posted body should ben
    {
    "from": ["Ben Bitdiddle <ben@foocorp.com"],
    "to": ["Ben Bitdiddle <ben@foocorp.com>", "cc-address@gmail.com"],
    "bcc": ["bcc-address@yahoo.com"],

    "subject": "Dinner at 7 tonight?",
    "html": "<html><body>....</body></html>",
    "files": [<file_id>, <file_id>, ...],

    // Optional
    "track_opened": false,
    ...
    }

    of if replying to an existing thread


    {
    "from": ["Ben Bitdiddle <ben@foocorp.com"],
    "to_thread": <thread_id>,

    // Optional
    "add_recipients": ["foo@gmail.com.com"],
    "remove_recipients": ["bar@gmail.com"],

    "html": "<html><body>....</body></html>",
    "files": [<file_id>, <file_id>, ...],

<!--    // Optional
    "track_opened": false,
    "append_quoted_text": true,
--> ...
}

    # if type(recipients) != list:
    #     recipients = [recipients]

    # send(account, recipients, subject, body, attachments)

"""


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
        parameters = json.loads(request.data)
        result = get_webhook_client().register_hook(g.namespace.id, parameters)
        return Response(result, mimetype='application/json')
    except (zerorpc.RemoteError, ValueError):
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

        try:
            data = json.loads(request.data)
            # We only support updates to the 'active' flag.
            if data.keys() != ['active']:
                raise ValueError

            if data['active']:
                get_webhook_client().start_hook(public_id)
            else:
                get_webhook_client().stop_hook(public_id)
            return jsonify({"success": True})

        except ValueError:
            return err(400, 'Malformed webhook request')

        except zerorpc.RemoteError:
            return err(404, "Couldn't find webhook with id {}"
                       .format(public_id))


@app.route('/webhooks/<public_id>', methods=['DELETE'])
def webhooks_delete_api(public_id):
    raise NotImplementedError
