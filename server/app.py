from gevent import monkey; monkey.patch_all()

import logging as log
from tornado.log import enable_pretty_logging
enable_pretty_logging()
from flask import Flask, request, redirect, make_response, render_template
from socketio import socketio_manage
from socketio.namespace import BaseNamespace
from socket_rpc import SocketRPC
import api
from models import db_session, User
import werkzeug.serving
import google_oauth
import sessionmanager
import json
from util import validate_email
from securecookie import SecureCookieSerializer


# Local development
APP_URL = 'localhost'
APP_PORT = 8888

COOKIE_SECRET = "32oETzKXQAGaYdkL5gEmGeJJFuYh7EQnp2XdTP1o/Vo="
GOOGLE_REDIRECT_URI ="http://localhost:8888/auth/authdone"


sc = SecureCookieSerializer(COOKIE_SECRET)

# The socket.io namespace
class WireNamespace(BaseNamespace):

    def initialize(self):
        self.user = None
        self.rpc = SocketRPC()


    def recv_connect(self):
        """ First connetion. This doesn't really get sent... """
        print 'received connect. is this a reconnect?', self
        # return True


    def recv_message(self, message):
        # TODO check auth everytime?
        log.info(message)

        query = db_session.query(User).filter(User.g_email == 'mgrinich@gmail.com')
        res = query.all()
        assert len(res) == 1
        user = res[0]

        response_text = self.rpc.run(api, message, user)

        # Send response
        self.send(response_text, json=True)
        return True

    def recv_error(self):
        log.error("recv_error %s" % self)
        return True

    def recv_disconnect(self):
        log.warning("WS Disconnected")
        self.disconnect(silent=True)
        return True


# TODO switch to regular flask user login stuff
# https://flask-login.readthedocs.org/en/latest/#how-it-works
def get_user(request):
    """ Gets a user object for the current request """
    session_token = sc.deserialize('session', request.cookies.get('session') )
    if not session_token: return None
    user_session  = sessionmanager.get_session(session_token)
    if not user_session: return None
    query = db_session.query(User).filter(User.g_email == user_session.email_address)
    user = query.all()[0]
    return user


app = Flask(__name__, static_folder='../web_client', static_url_path='', template_folder='templates')
@app.route('/')
def index():
    user = get_user(request)
    return render_template('index.html',
                            name = user.g_email if user else " ",
                            logged_in = bool(user))


@app.route('/app')
@app.route('/app/')  # TOFIX not sure I need to do both
def static_app_handler():
    return app.send_static_file('index.html')


@app.route('/auth/validate')
def validate_email_handler():
    """ Validate's the email to google MX records """
    email_address = request.args.get('email_address')
    is_valid_dict = validate_email(email_address)
    return json.dumps(is_valid_dict)


@app.route('/auth/authstart')
def auth_start_handler():
    assert 'email_address' in request.args
    email_address = request.args.get('email_address')
    log.info("Starting auth with email %s" % email_address)
    url = google_oauth.authorize_redirect_url(
                    GOOGLE_REDIRECT_URI,
                    email_address = email_address)
    return redirect(url)


@app.route('/auth/authdone')
def auth_done_handler():
    # Closes the popup
    response = make_response("<script type='text/javascript'>parent.close();</script>")
    try:
        assert 'code' in request.args
        authorization_code = request.args['code']
        oauth_response = google_oauth.get_authenticated_user(
                            authorization_code,
                            redirect_uri=GOOGLE_REDIRECT_URI)
        assert 'email' in oauth_response
        assert 'access_token' in oauth_response
        assert 'refresh_token' in oauth_response
        new_user_object = sessionmanager.make_user(oauth_response)
        new_session = sessionmanager.create_session(new_user_object.g_email)
        log.info("Successful login. Setting cookie: %s" % new_session.session_token)

        secure_cookie = sc.serialize('session', new_session.session_token )
        response.set_cookie('session', secure_cookie)  # TODO when to expire?

    except Exception, e:
        # TODO handler error better here. Write an error page to user.
        log.error(e)
        error_str = request.args['error']
        log.error("Google auth failed: %s" % error_str)
    finally:
        return response


@app.route("/auth/logout")
def logout():
    response = make_response(redirect('/'))
    response.set_cookie('session', '', expires=0)
    return response


@app.route("/wire/<path:path>")
def run_socketio(path):
    log.warning('Connecting socket. Probably handle auth here...')
    # TODO authenticate user session
    socketio_manage(request.environ, {'': WireNamespace})
    return make_response('', 200)  # Flask needs this


# TODO downloader and uploaders.

# class FileDownloadHandler(BaseHandler):
#     @tornado.web.authenticated
#     def get(self):

#         args = self.request.arguments

#         uid = args['uid'][0]
#         section_index = args['section_index'][0]
#         content_type = args['content_type'][0]
#         data_encoding = args['encoding'][0]
#         filename = args['filename'][0]

#         self.set_header ('Content-Type', content_type)
#         self.set_header ('Content-Disposition', 'attachment; filename=' + filename)

#         crispin_client = sessionmanager.get_crispin_from_email(self.get_current_user().g_email)
#         data = crispin_client.fetch_msg_body(uid, section_index)

#         decoded = encoding.decode_data(data, data_encoding)
#         self.write(decoded)




# class FileUploadHandler(BaseHandler):

#     @tornado.web.authenticated
#     def post(self):

#         try:
#             uploaded_file = self.request.files['file'][0]  # wacky

#             uploads_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "../uploads/")
#             if not os.path.exists(uploads_path):
#                 os.makedirs(uploads_path)

#             write_filename = str(time.mktime(time.gmtime())) +'_' + uploaded_file.filename
#             write_path = os.path.join(uploads_path, write_filename)

#             f = open(write_path, "w")
#             f.write(uploaded_file.body)
#             f.close()

#             log.info("Uploaded file: %s (%s) to %s" % (uploaded_file.filename, uploaded_file.content_type, write_path))

#             # TODO
#         except Exception, e:
#             log.error(e)
#             raise tornado.web.HTTPError(500)



@werkzeug.serving.run_with_reloader
def startserver(port=APP_PORT):
    app.debug = True
    log.info("Starting Flask...")

    import os
    from werkzeug.wsgi import SharedDataMiddleware

    ws_app = SharedDataMiddleware(app, {
            '/app/': os.path.join(os.path.dirname(__file__), '../web_client')
        })

    if APP_PORT != 80:
        log.info('Listening on http://'+APP_URL+':'+str(APP_PORT)+"/")
    else:
        log.info('Listening on http://'+APP_URL+'/')

    from socketio.server import SocketIOServer  # inherits gevent.pywsgi.WSGIServer
    SocketIOServer(('localhost', port), ws_app,
        resource="wire", policy_server=True).serve_forever()


# Need to do something like this to close existing socket connections gracefully
# def stopsubmodules():
#     sessionmanager.stop_all_crispins()
#     # also stop idler if necessary
