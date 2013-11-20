import os
import json

from StringIO import StringIO

from gevent import monkey; monkey.patch_all()

from flask import Flask, request, redirect, make_response, render_template
from flask import Response, jsonify, abort, send_file
from werkzeug.wsgi import SharedDataMiddleware
from socketio import socketio_manage
from socketio.namespace import BaseNamespace
from securecookie import SecureCookieSerializer

import zerorpc

from socket_rpc import SocketRPC
from models import db_session, Message, Block, Collection, IMAPAccount
from models import Namespace
from .log import get_logger
log = get_logger()

import google_oauth
import sessionmanager

from ..util.url import validate_email

from ..util.img import generate_thumbnail
from .config import config

COOKIE_SECRET = config.get("COOKIE_SECRET", None)
assert COOKIE_SECRET, "Missing secret for secure cookie generation"
sc = SecureCookieSerializer(COOKIE_SECRET)

# TODO switch to regular flask user login stuff
# https://flask-login.readthedocs.org/en/latest/#how-it-works
def get_user(request):
    """ Gets a user object for the current request """
    session_token = sc.deserialize('session', request.cookies.get('session') )
    if not session_token: return None
    user_session  = sessionmanager.get_session(session_token)
    if not user_session: return None
    return user_session.user

# TODO this is a HACK and needs to be changed before multiaccount support
def get_account(request):
    user = get_user(request)
    if user is None or len(user.imapaccounts) == 0:
        return None
    return user.imapaccounts[0]

app = Flask(__name__, static_folder='../../../web_client', static_url_path='', template_folder='templates')

@app.route('/')
def index():
    account = get_account(request)
    return render_template('index.html',
                            name = account.email_address if account else "",
                            logged_in = bool(account))

@app.route('/app')
@app.route('/app/')  # TOFIX not sure I need to do both
def static_app_handler():
    """ Just returns the static app files """

    if not get_user(request):
        return redirect('/')
    return app.send_static_file('index.html')

@app.route('/auth/validate')
def validate_email_handler():
    """ Validate's the email to google MX records """
    email_address = request.args.get('email_address')
    is_valid_dict = validate_email(email_address)
    return json.dumps(is_valid_dict)

@app.route('/auth/redirect_url')
def auth_redirect_url():
    email_address = request.args.get('email_address')
    log.info("Starting auth with email %s" % email_address)
    url = google_oauth.authorize_redirect_url(
                    app.config['GOOGLE_REDIRECT_URI'],
                    email_address = email_address)
    return jsonify(url=url)

@app.route('/auth/authstart')
def auth_start_handler():
    """ Creates oauth URL and redirects to Google """
    assert 'email_address' in request.args

    return render_template('to_gmail.html')
                            # redirect_url=url)

@app.route('/auth/authdone')
def auth_done_handler():
    """ Callback from google oauth. Verify and close popup """
    # Closes the popup
    response = make_response("<script type='text/javascript'>parent.close();</script>")
    assert 'code' in request.args
    authorization_code = request.args['code']
    oauth_response = google_oauth.get_authenticated_user(
                        authorization_code,
                        redirect_uri=app.config['GOOGLE_REDIRECT_URI'])
    print oauth_response
    assert 'email' in oauth_response
    assert 'access_token' in oauth_response
    assert 'refresh_token' in oauth_response

    new_account = sessionmanager.make_account(oauth_response)
    new_session = sessionmanager.create_session(new_account.user)

    log.info("Successful login. Setting cookie: %s" % new_session.token)

    secure_cookie = sc.serialize('session', new_session.token )
    response.set_cookie('session', secure_cookie,
            domain=app.config['SESSION_COOKIE_DOMAIN'])

    # kick off syncing the new account's mail
    sync_srv_loc = config.get('CRISPIN_SERVER_LOC', None)
    c = zerorpc.Client(timeout=3000)
    c.connect(sync_srv_loc)
    sync_response = c.start_sync(new_account.email_address)
    log.info("Asked sync service to start syncing new account: {0}".format(
        sync_response))

    # except Exception, e:
    #     # TODO handler error better here. Write an error page to user.
    #     log.error(e)
    #     error_str = request.args['error']
    #     log.error("Google auth failed: %s" % error_str)
    # finally:
    return response

@app.route("/auth/logout")
def logout():
    """ Delete session cookie and reload """
    response = make_response(redirect('/'))
    response.set_cookie('session', '', expires=0, domain=app.config['SESSION_COOKIE_DOMAIN'])
    return response

@app.route("/wire/<path:path>")
def run_socketio(path):

    real_request = request._get_current_object()
    account = get_account(request)
    if account:
        log.info('Successful socket auth for {0}'.format(account.email_address))
        socketio_manage(request.environ, {
                        '/wire': WireNamespace},
                        request=real_request)
    else:
        log.error("No user object for request: %s" % request)

    return Response()

active_sockets = {}

# The socket.io namespace
class WireNamespace(BaseNamespace):

    def __init__(self, *args, **kwargs):
        request = kwargs.get('request', None)
        self.ctx = None
        if request:   # Save request context for other ws msgs
            self.ctx = app.request_context(request.environ)
            self.ctx.push()
            app.preprocess_request()
            del kwargs['request']
        super(WireNamespace, self).__init__(*args, **kwargs)


    def initialize(self):
        self.user = None
        self.rpc = SocketRPC()

    # def get_initial_acl(self):
    #     return ['on_connect', 'on_public_method']

    def recv_connect(self):
        log.info("Socket connected.")
        active_sockets[id(self)] = self
        log.info("%i active socket%s" % (len(active_sockets),
                                '' if len(active_sockets) == 1 else 's'))

    def recv_message(self, message):
        log.info(message)

        # TODO: Make this an @authenticated decorator someday
        user_id = get_user(request)
        assert user_id

        api_srv_loc = config.get('API_SERVER_LOC', None)
        assert api_srv_loc
        c = zerorpc.Client(timeout=3000)
        c.connect(api_srv_loc)

        response_text = self.rpc.run(c, message, user_id)

        # Send response
        self.send(response_text, json=True)
        return True

    def recv_error(self):
        log.error("recv_error %s" % self)
        return True

    def recv_disconnect(self):
        log.warning("WS Disconnected")
        self.disconnect(silent=True)
        del active_sockets[id(self)]

        log.info("%i active socket%s" % (len(active_sockets),
                                '' if len(active_sockets) == 1 else 's'))
        return True

    def disconnect(self, *args, **kwargs):
        # if self.ctx:
        #     self.ctx.pop()   # Not sure why this causes an exception
        super(WireNamespace, self).disconnect(*args, **kwargs)

@app.route('/file_upload', methods=['GET', 'POST'])
def upload_file_handler():
    account = get_account(request)
    if not account:
        log.error("No user session for upload attempt")
        abort(401)
        return

    log.info(request.files)
    # XXX TODO pull the collection ID out of the POST request
    collection_id = 1
    collection = db_session.query(Collection).filter_by(id=collection_id).first()
    if not collection:
        # XXX not actually sure what 'type' field is for yet
        collection = Collection(id=1, type="gallery")
        db_session.add(collection)
        db_session.commit()
    if request.method == 'POST' and 'file' in request.files:
        uploaded_file = request.files['file']

        meta = Message(namespace_id=account.namespace.id)
        part = Block(
                message=meta,
                filename=uploaded_file.filename,
                is_inboxapp_attachment=True,
                collection=collection)
        part.content_type = uploaded_file.content_type
        log.info("New uploaded file %s" % part.filename)
        part.save(uploaded_file.read())  # TODO consider sending the stream object
        log.info("Saved upload to S3 with hash {0}".format(part.data_sha256))

        # Return content_id for upload
        # TODO right now the content_id is just the upload's hash
        # later we should salt this with something
        part.content_id = part.data_sha256
        db_session.add(meta)
        db_session.add(part)
        db_session.commit()
        return part.data_sha256

    log.error("What are we trying to upload?")
    return Response()

# XXX TODO don't download unsalted hashes here
@app.route('/<email>/img/<sha256>', methods=['GET'])
def download_handler(email, sha256):
    # grab image from S3 and pass it on
    part = db_session.query(Block).join(Message) \
            .join(Namespace).join(IMAPAccount).filter(
            IMAPAccount.email_address==email,
            Block.data_sha256==sha256).first()
    if not part:
        abort(404)
        return
    # XXX don't hardcode MIMEtype
    return send_file(StringIO(part.get_data()), mimetype='image/jpeg')

@app.route('/<email>/img/<sha256>/thumb', methods=['GET'])
def thumb_download_handler(email, sha256):
    # grab image from S3 and pass it on
    part = db_session.query(Block).join(Message).filter(
            Message.g_email==email,
            Block.data_sha256==sha256).first()
    if not part:
        abort(404)
        return
    # XXX don't hardcode MIMEtype
    thumb_blob = generate_thumbnail(part.get_data())
    return send_file(StringIO(thumb_blob), mimetype='image/jpeg')

# XXX need to mangle the URL somehow
@app.route('/<email>/gallery/<id>', methods=['GET'])
def gallery_handler(email, id):
    log.info("email: '{0}' / id: '{1}'".format(email, id))
    # no auth required to view galleries
    # XXX limit by type
    images = db_session.query(Block).filter_by(
            collection_id=id).all()
    return render_template('gallery.html', images=images, email=email)

# Catchall
# @app.route('/', defaults={'path': ''})
# @app.route('/<path:path>')
# def catch_all(path):
#     return 'You want path: %s' % path

@app.route("/<blockhash>", subdomain="msg-store")
def block_retrieval(blockhash):
    if not blockhash: return None

    account = get_account(request)
    if not account: return None

    return account.email_address

    query = db_session.query(Block).filter(Block.data_sha256 == blockhash)

    part = query.all()
    if not part: return None
    part = part[0]

    s = []
    for k,v in part.__dict__.iteritems():
        try:
            s.append(json.dumps([k,v]))
        except Exception:
            pass

    return json.dumps(s)

# TODO do reloading with gunicorn
def startserver(app_url, app_port):

    if not isinstance(app_port, int):
        log.warning("Specified port to listen should be an integer")
        app_port = int(app_port)

    log.info("Starting Flask...")
    app.debug = True

    domain_name = config.get("SERVER_DOMAIN_NAME", None)
    assert domain_name, "Need domain name for Google oauth callback"
    app.config['GOOGLE_REDIRECT_URI'] ="https://%s/auth/authdone" % domain_name

    app.config['SESSION_COOKIE_DOMAIN'] = '.inboxapp.com'

    app.config['MAX_CONTENT_LENGTH'] = 300 * 1024 * 1024  # 300 MB


    ws_app = SharedDataMiddleware(app, {
            '/app/': os.path.join(os.path.dirname(__file__), '../web_client')
    })


    log.info('Listening on http://'+app_url+':'+str(app_port)+"/")


    from socketio.server import SocketIOServer  # inherits gevent.pywsgi.WSGIServer
    SocketIOServer((app_url, app_port), ws_app,
        resource="wire", policy_server=True).serve_forever()


# Need to do something like this to close existing socket connections gracefully
# def stopsubmodules():
#     sessionmanager.stop_all_crispins()
#     # also stop idler if necessary
