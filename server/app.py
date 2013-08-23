import os.path
import logging as log
import time

import tornado.ioloop
import tornado.web
import tornado.httpclient
from tornado import escape

from tornado.log import enable_pretty_logging
enable_pretty_logging()


from urllib import urlencode
from securecookie import SecureCookieSerializer

import google_oauth
import sessionmanager

from tornadio2 import TornadioRouter
from socket_rpc import SocketRPC
from tornadio2 import proto
import dns.resolver

import encoding
import api
from models import db_session, User

COOKIE_SECRET = "32oETzKXQAGaYdkL5gEmGeJJFuYh7EQnp2XdTP1o/Vo="
MAILGUN_API_PUBLIC_KEY = "pubkey-8nre-3dq2qn8-jjopmq9wiwu4pk480p2"

class Application(tornado.web.Application):
    def __init__(self):

        PATH_TO_WEB_CLIENT = os.path.join(os.path.dirname(__file__), "../web_client")
        PATH_TO_STATIC = os.path.join(os.path.dirname(__file__), "../static")

        settings = dict(
            static_path=os.path.join(PATH_TO_STATIC),
            xsrf_cookies=False,  # debug

            debug=True,
            flash_policy_port=843,
            flash_policy_file=os.path.join(PATH_TO_STATIC + "/flashpolicy.xml"),
            socket_io_port=8001,

            login_url="/",  # for now
            redirect_uri="http://localhost:8888/auth/authdone",

            cookie_secret=COOKIE_SECRET,
        )

        PingRouter = TornadioRouter(WireConnection, namespace='wire')

        handlers = PingRouter.apply_routes([
            (r"/", MainHandler),

            (r"/auth/validate", ValidateEmailHandler),
            (r"/auth/authstart", AuthStartHandler),
            (r"/auth/authdone", AuthDoneHandler),

            (r"/auth/logout", LogoutHandler),

            (r'/app/(.*)', AngularStaticFileHandler, {'path': PATH_TO_WEB_CLIENT,
                                           'default_filename':'index.html'}),
            (r'/app', AppRedirectHandler),
            (r'/file_download', FileDownloadHandler),
            (r'/file_upload', FileUploadHandler),

            (r'/(?!wire|!app|file)(.*)', tornado.web.StaticFileHandler, {'path': PATH_TO_STATIC,
                                           'default_filename':'index.html'}),
        ])

        tornado.web.Application.__init__(self, handlers, **settings)


class BaseHandler(tornado.web.RequestHandler):
    # TODO put authentication stuff here
    def get_current_user(self):
        session_token = self.get_secure_cookie("session")
        user_session  = sessionmanager.get_session(session_token)
        if not user_session: return None
        query = db_session.query(User).filter(User.g_email == user_session.email_address)
        user = query.all()[0]
        return user


class MainHandler(BaseHandler):
    def get(self):
        self.render("templates/index.html", name = self.current_user.g_email if self.current_user else " ",
                                            logged_in = bool(self.current_user) )


class ValidateEmailHandler(BaseHandler):

    def get(self):
        address_text = self.get_argument('email_address', default=None)
        if not address_text:
            raise tornado.web.HTTPError(500, "email_address is required")

        args = {
            "address": address_text,
        }
        MAILGUN_VALIDATE_API_URL = "https://api.mailgun.net/v2/address/validate?" + urlencode(args)

        request = tornado.httpclient.HTTPRequest(MAILGUN_VALIDATE_API_URL)
        request.auth_username = 'api'
        request.auth_password = MAILGUN_API_PUBLIC_KEY

        try:
            sync_client = tornado.httpclient.HTTPClient()  # Todo make async?
            response = sync_client.fetch(request)
        except tornado.httpclient.HTTPError, e:
            response = e.response
            pass  # handle below
        except Exception, e:
            log.error(e)
            raise tornado.web.HTTPError(500, "Internal email validation error.")
        if response.error:
            error_dict = escape.json_decode(response.body)
            log.error(error_dict)
            raise tornado.web.HTTPError(500, "Internal email validation error.")

        body = escape.json_decode(response.body)

        is_valid = body['is_valid']
        if is_valid:
            # Must have Gmail or Google Apps MX records
            domain = body['parts']['domain']
            answers = dns.resolver.query(domain, 'MX')



            gmail_mx_servers = [
                    # Google apps for your domain
                    'aspmx.l.google.com.',
                    'aspmx2.googlemail.com.',
                    'aspmx3.googlemail.com.',
                    'aspmx4.googlemail.com.',
                    'aspmx5.googlemail.com.',
                    'alt1.aspmx.l.google.com.',
                    'alt2.aspmx.l.google.com.',
                    'alt3.aspmx.l.google.com.',
                    'alt4.aspmx.l.google.com.',

                    # Gmail
                    'gmail-smtp-in.l.google.com.',
                    'alt1.gmail-smtp-in.l.google.com.',
                    'alt2.gmail-smtp-in.l.google.com.',
                    'alt3.gmail-smtp-in.l.google.com.',
                    'alt4.gmail-smtp-in.l.google.com.'
                     ]

            # All relay servers must be gmail
            for rdata in answers:
                if not str(rdata.exchange).lower() in gmail_mx_servers:
                    is_valid = False
                    log.error("Non-Google MX record: %s" % str(rdata.exchange))

        ret = dict(
            valid_for_inbox = is_valid,
            did_you_mean = body['did_you_mean'],
            valid_address = body['address']
        )
        data_json = tornado.escape.json_encode(ret)
        self.write(data_json)


class AuthStartHandler(BaseHandler):
    @tornado.web.asynchronous
    def get(self):
        url = google_oauth.authorize_redirect_url(
                        self.settings['redirect_uri'],
                        email_address = self.get_argument('email_address', default=None))
        self.redirect(url)


class AuthDoneHandler(BaseHandler):
    def get(self):
        authorization_code = self.get_argument("code", None)
        error = self.get_argument("error", None)

        try:
            assert authorization_code
            response = google_oauth.get_authenticated_user(
                                authorization_code,
                                redirect_uri=self.settings['redirect_uri'])
            assert 'email' in response
            assert 'access_token' in response
            assert 'refresh_token' in response
            new_user_object = sessionmanager.make_user(response)
            new_session = sessionmanager.create_session(new_user_object.g_email)
            log.info("Successful login. Setting cookie: %s" % new_session.session_token)
            self.set_secure_cookie("session", new_session.session_token)

        except Exception, e:
            # TODO handler error better here. Write an error page to user.
            log.error("Google auth failed: %s" % error)
        finally:
            # Closes the window
            self.write("<script type='text/javascript'>parent.close();</script>")  # closes window
            self.flush()
            self.finish()


class LogoutHandler(BaseHandler):
    def get(self):
        self.clear_cookie("session")
        sessionmanager.stop_all_crispins()
        self.redirect("/")


class AngularStaticFileHandler(tornado.web.StaticFileHandler):
    def get(self, path, **kwargs):
        if not self.get_secure_cookie("session"):  # check auth
            self.redirect(self.settings['login_url'])
            return
        super(AngularStaticFileHandler, self).get(path, **kwargs)

    # DEBUG: Don't cache anything right now --
    def set_extra_headers(self, path):
        self.set_header("Cache-control", "no-cache")



class AppRedirectHandler(BaseHandler):
    # TODO put authentication stuff here
    @tornado.web.authenticated
    def get(self):
        self.redirect('/app/')



class FileDownloadHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):

        args = self.request.arguments

        uid = args['uid'][0]
        section_index = args['section_index'][0]
        content_type = args['content_type'][0]
        data_encoding = args['encoding'][0]
        filename = args['filename'][0]

        self.set_header ('Content-Type', content_type)
        self.set_header ('Content-Disposition', 'attachment; filename=' + filename)

        crispin_client = sessionmanager.get_crispin_from_email(self.get_current_user().g_email)
        data = crispin_client.fetch_msg_body(uid, section_index)

        decoded = encoding.decode_data(data, data_encoding)
        self.write(decoded)




class FileUploadHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):

        try:
            uploaded_file = self.request.files['file'][0]  # wacky

            uploads_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "../uploads/")
            if not os.path.exists(uploads_path):
                os.makedirs(uploads_path)

            write_filename = str(time.mktime(time.gmtime())) +'_' + uploaded_file.filename
            write_path = os.path.join(uploads_path, write_filename)

            f = open(write_path, "w")
            f.write(uploaded_file.body)
            f.close()

            log.info("Uploaded file: %s (%s) to %s" % (uploaded_file.filename, uploaded_file.content_type, write_path))

            # TODO
        except Exception, e:
            log.error(e)
            raise tornado.web.HTTPError(500)



# Websocket
class WireConnection(SocketRPC):
    clients = set()


    def __init__(self, session, endpoint=None):
        self.session = session
        self.endpoint = endpoint
        self.is_closed = False
        self.user = None


    def on_open(self, request):
        try:
            s = SecureCookieSerializer(COOKIE_SECRET)
            session_token = s.deserialize('session', request.cookies['session'].value)
            user_session  = sessionmanager.get_session(session_token)
            if not user_session:
                log.warning("Unauthenticated socket connection attempt")
                raise tornado.web.HTTPError(401)
            query = db_session.query(User).filter(User.g_email == user_session.email_address)
            res = query.all()
            assert len(res) == 1
            self.user = res[0]

        except Exception, e:
            log.warning("Unauthenticated socket connection attempt")
            raise tornado.web.HTTPError(401)
        log.info("Web client connected.")
        self.clients.add(self)


    def on_close(self):
        log.info("Web client disconnected")
        self.clients.remove(self)


    def close(self):
        """Forcibly close client connection"""
        self.session.close(self.endpoint)
        # TODO: Notify about unconfirmed messages?


    # TODO add authentication thing here to check for session token
    def on_message(self, message_body):
        response_text = self.run(api, message_body)

        # Send the message
        msg = proto.message(self.endpoint, response_text)
        self.session.send_message(msg)





def idler_callback():
    log.info("Received idler callback.")
    for connection in WireConnection.clients:
        connection.send_message_notification()



def startserver(port):

    app = Application()
    app.listen(port)


    tornado.log.enable_pretty_logging()
    tornado.autoreload.start()
    tornado.autoreload.add_reload_hook(stopsubmodules)


    global idler
    # idler = Idler('mgrinich@gmail.com', 'ya29.AHES6ZSUdWE6lrGFZOFSXPTuKqu1cnWKwHnzlerRoL52UZA1m88B3oI',
    #               ioloop=loop,
    #               event_callback=idler_callback,
    #               # folder=crispin_client.all_mail_folder_name())
    #               folder="Inbox")
    # idler.connect()
    # idler.idle()

    # Must do this last
    loop = tornado.ioloop.IOLoop.instance()
    log.info('Starting Tornado on port %s' % str(port))

    loop.start()



def stopsubmodules():
    # if idler:
    #     idler.stop()

    sessionmanager.stop_all_crispins()


def stopserver():
    stopsubmodules()
    # Kill IO loop next iteration
    log.info("Stopping Tornado")
    ioloop = tornado.ioloop.IOLoop.instance()
    ioloop.add_callback(ioloop.stop)
