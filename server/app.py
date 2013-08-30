from gevent import monkey; monkey.patch_all()

import logging as log
from tornado.log import enable_pretty_logging; enable_pretty_logging()
from flask import Flask, request, redirect, make_response, render_template, Response
from socketio import socketio_manage
from socketio.namespace import BaseNamespace
from socket_rpc import SocketRPC
import api
from models import db_session, User, MessagePart
import werkzeug.serving
from werkzeug.wsgi import SharedDataMiddleware

import google_oauth
import sessionmanager
import json
from util import validate_email
from securecookie import SecureCookieSerializer
import zerorpc
from os import environ
import os
from urlparse import urlparse, urlunparse

COOKIE_SECRET = "32oETzKXQAGaYdkL5gEmGeJJFuYh7EQnp2XdTP1o/Vo="
sc = SecureCookieSerializer(COOKIE_SECRET)


# TODO switch to regular flask user login stuff
# https://flask-login.readthedocs.org/en/latest/#how-it-works
def get_user(request):
    """ Gets a user object for the current request """
    session_token = sc.deserialize('session', request.cookies.get('session') )
    if not session_token: return None
    user_session  = sessionmanager.get_session(session_token)
    if not user_session: return None
    query = db_session.query(User).filter(User.g_email == user_session.g_email)
    user = query.all()[0]
    return user


app = Flask(__name__, static_folder='../web_client', static_url_path='', template_folder='templates')

# app.config['STATIC_ROOT'] = 'www..inboxapp.com:8888'


app.add_url_rule('/<path:filename>', endpoint='static',
                 view_func=app.send_static_file, subdomain='www')


@app.route('/', subdomain="www")
def index():
    user = get_user(request)
    return render_template('index.html',
                            name = user.g_email if user else " ",
                            logged_in = bool(user))

@app.before_request
def redirect_nonwww():
    """Redirect non-www requests to www.
       Let's just stay way from apex domains. """
    urlparts = urlparse(request.url)

    if urlparts.netloc == app.config['SERVER_NAME']:
        urlparts_list = list(urlparts)
        urlparts_list[1] = "www.%s" % app.config['SERVER_NAME']
        return redirect(urlunparse(urlparts_list), code=301)


@app.route('/app', subdomain="www")
@app.route('/app/', subdomain="www")  # TOFIX not sure I need to do both
def static_app_handler():
    """ Just returns the static app files """

    if not get_user(request):
        return redirect('/')
    return app.send_static_file('index.html')


@app.route('/auth/validate', subdomain="www")
def validate_email_handler():
    """ Validate's the email to google MX records """
    email_address = request.args.get('email_address')
    is_valid_dict = validate_email(email_address)
    return json.dumps(is_valid_dict)


@app.route('/auth/authstart', subdomain="www")
def auth_start_handler():
    """ Creates oauth URL and redirects to Google """
    assert 'email_address' in request.args
    email_address = request.args.get('email_address')
    log.info("Starting auth with email %s" % email_address)
    url = google_oauth.authorize_redirect_url(
                    app.config['GOOGLE_REDIRECT_URI'],
                    email_address = email_address)
    return redirect(url)


@app.route('/auth/authdone', subdomain="www")
def auth_done_handler():
    """ Callback from google oauth. Verify and close popup """
    # Closes the popup
    response = make_response("<script type='text/javascript'>parent.close();</script>")
    try:
        assert 'code' in request.args
        authorization_code = request.args['code']
        oauth_response = google_oauth.get_authenticated_user(
                            authorization_code,
                            redirect_uri=app.config['GOOGLE_REDIRECT_URI'])
        assert 'email' in oauth_response
        assert 'access_token' in oauth_response
        assert 'refresh_token' in oauth_response
        new_user_object = sessionmanager.make_user(oauth_response)
        new_session = sessionmanager.create_session(new_user_object.g_email)
        log.info("Successful login. Setting cookie: %s" % new_session.session_token)

        secure_cookie = sc.serialize('session', new_session.session_token )
        response.set_cookie('session', secure_cookie, domain=".inboxapp.com")  # TODO when to expire?

    except Exception, e:
        # TODO handler error better here. Write an error page to user.
        log.error(e)
        error_str = request.args['error']
        log.error("Google auth failed: %s" % error_str)
    finally:
        return response



@app.route("/auth/logout", subdomain="www")
def logout():
    """ Delete session cookie and reload """
    response = make_response(redirect('/'))
    response.set_cookie('session', '', expires=0, domain=".inboxapp.com")
    return response





@app.route("/wire/<path:path>", subdomain="www")
def run_socketio(path):
    # TODO authenticate user session
    real_request = request._get_current_object()
    user = get_user(request)
    if user:
        log.info('Successful socket auth for %s' % user.g_email)
        socketio_manage(request.environ, {
                        '/wire_namespace': WireNamespace},
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
        # TODO check auth everytime?
        log.info(message)

        query = db_session.query(User).filter(User.g_email == 'mgrinich@gmail.com')
        res = query.all()
        assert len(res) == 1
        user = res[0]


        api_srv_loc = environ.get('API_SERVER_LOC', None)
        assert api_srv_loc
        c = zerorpc.Client()
        c.connect(api_srv_loc)


        print 'Calling on', c
        print message
        response_text = self.rpc.run(c, message, user)


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

# Catchall
# @app.route('/', defaults={'path': ''})
# @app.route('/<path:path>')
# def catch_all(path):
#     return 'You want path: %s' % path



@app.route("/<blockhash>", subdomain="msg-store")
def block_retrieval(blockhash):
    if not blockhash: return None

    if not get_user(request): return None

    return get_user(request).g_email

    query = db_session.query(MessagePart).filter(MessagePart.data_sha256 == blockhash)

    part = query.all()
    if not part: return None
    part = part[0]


    s = []
    for k,v in part.__dict__.iteritems():
        try:
            s.append(json.dumps([k,v]))
        except Exception, e:
            pass

    return json.dumps(s)


    # return "MSG-STORE RETREIVE BLOCK WITH HASH %s" % blockhash



@app.errorhandler(404)
def page_not_found(e):
    return app.send_static_file('404.html')


# TODO do reloading with gunicorn
def startserver(app_url, app_port):

    if not isinstance(app_port, int):
        log.warning("Specified port to listen should be an integer")
        app_port = int(app_port)



    log.info("Starting Flask...")
    app.debug = True

    # TODO remove port from this for production
    app.config['SERVER_NAME'] = '%s:%i' % (app_url, app_port)
    app.config['SESSION_COOKIE_DOMAIN'] = '.inboxapp.com'
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_NAME'] = 'inbox_session'
    app.config['GOOGLE_REDIRECT_URI'] ="http://%s/auth/authdone" % app.config['SERVER_NAME']


    # app.config['PREFERRED_URL_SCHEME'] = 'https'
    app.config['SECRET_KEY'] = 'asdfhouh32ouhwlnsfdoslnsa;hdof'


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
