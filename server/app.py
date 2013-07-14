import os.path as os_path
import logging as log

import tornado.ioloop
import tornado.web
import tornado.template
import tornado.log
import tornado.options
import tornado.gen
import tornado.escape
from tornadio2 import SocketConnection, TornadioRouter, event

import tornadio2.gen

from models import *

from crispin import CrispinClient
from crispin import AuthenticationError
from securecookie import SecureCookieSerializer
from idler import Idler
import oauth2
import postel

import pymongo
from bson.objectid import ObjectId
import motor
import uuid



session_to_user = {}

email_address_to_crispins = {}

user_email_to_token = {}


PATH_TO_ANGULAR = os_path.join(os_path.dirname(__file__), "../angular")
PATH_TO_STATIC = os_path.join(os_path.dirname(__file__), "../static")




class Application(tornado.web.Application):
    def __init__(self):


        sync_db = pymongo.Connection().test
        try:
            sync_db.create_collection('chirps', size=10000, capped=True)
            log.info('Created capped collection "chirps" in database "test"')

        except pymongo.errors.CollectionInvalid:
            if 'capped' not in sync_db.chirps.options():
                print >> sys.stderr, (
                    'test.chirps exists and is not a capped collection,\n'
                    'please drop the collection and start this example app again.'
                )
                sys.exit(1)



        motor_client = motor.MotorClient()
        motor_client.open_sync()
        motor_db = motor_client.test

        # cursor_manager = CursorManager(motor_db)
        # cursor_manager.start()

        settings = dict(
            static_path=os_path.join(PATH_TO_STATIC),
            xsrf_cookies=True,  # debug
            debug=True,
            flash_policy_port=843,
            flash_policy_file=os_path.join(PATH_TO_STATIC + "/flashpolicy.xml"),
            socket_io_port=8001,

            cookie_secret="32oETzKXQAGaYdkL5gEmGeJJFuYh7EQnp2XdTP1o/Vo=",
            login_url="/auth/login",

            redirect_uri="http://localhost:8888/auth/authdone",

            google_consumer_key="786647191490.apps.googleusercontent.com",  # client ID
            google_consumer_secret="0MnVfEYfFebShe9576RR8MCK",  # aka client secret

            motor_db=motor_db
        )

        PingRouter = TornadioRouter(WireConnection, namespace='wire')

        handlers = PingRouter.apply_routes([
            (r"/", MainHandler),

            (r"/testsend", TestSendHandler),

            (r"/auth/authstart", AuthStartHandler),
            (r"/auth/authdone", AuthDoneHandler),

            (r"/auth/logout", LogoutHandler),

            (r'/app/(.*)', AngularStaticFileHandler, {'path': PATH_TO_ANGULAR, 
                                           'default_filename':'index.html'}),
            (r'/app', AppRedirectHandler),
            (r'/file', FileDownloadHandler),
            # /wire is the route for messages.
            (r'/(?!wire|!app|file)(.*)', tornado.web.StaticFileHandler, {'path': PATH_TO_STATIC, 
                                           'default_filename':'index.html'}),       
        ])

        tornado.web.Application.__init__(self, handlers, **settings)




class BaseHandler(tornado.web.RequestHandler):
    # TODO put authentication stuff here
    def get_current_user(self):
        session_key = self.get_secure_cookie("session")
        if not session_key in session_to_user: return None
        return session_to_user[session_key]
        # return tornado.escape.json_decode(user_json)

chirps = []

class MainHandler(BaseHandler):

    def get(self):


        # motor.Op(self.settings['motor_db'].chirps.insert, {
        #     'msg': 'somemsg',
        #     'ts': datetime.datetime.utcnow(),
        #     '_id': ObjectId() })


        # if chirps:
        #     last_chirp = chirps[-1]
        #     query = {
        #         'ts': {'$gte': last_chirp['ts']},
        #         '_id': {'$ne': last_chirp['_id']}
        #     }
        # else:
        #     query = {}


        # def _on_response(response, error):
        #     # memmory cache
        #     chirps.extend([response])

        #     # We have new data for the client.
        #     log.debug('New data: ' + str(response)[:150])
        #     print 'new chirp' + str(response)



        # cursor = self.settings['motor_db'].chirps.find(query)
        # cursor.tail(_on_response)



        logged_in = False
        name = " "

        if self.current_user:
            name = self.current_user["name"]
            logged_in = True

        self.render("templates/index.html", name = name,
                                            logged_in = logged_in )



class TestSendHandler(BaseHandler):

    def get(self):
        s = postel.SMTP('mgrinich@gmail.com', oauth2.GoogleOAuth2Mixin.access_token)
        s.setup()
        s.send_mail("Test message", "Body content of test message!")
        s.quit()



class AuthStartHandler(BaseHandler, oauth2.GoogleOAuth2Mixin):
    @tornado.web.asynchronous
    def get(self):
        self.authorize_redirect()



class AuthDoneHandler(BaseHandler, oauth2.GoogleOAuth2Mixin):
    @tornado.web.asynchronous
    @tornado.gen.engine
    def get(self):
        if not self.get_argument("code", None): self.fail()

        authorization_code = self.get_argument("code", None)

        response = yield tornado.gen.Task(self.get_authenticated_user, authorization_code)

        if response is None: self.fail()
        user_json = response.body

        user = tornado.escape.json_decode(user_json)

        email_address = user['email']
        oauth_token = oauth2.GoogleOAuth2Mixin.access_token


        # Shut down old session. Auth is not longer valid
        if email_address in email_address_to_crispins:
            email_address_to_crispins[email_address].stop()


        try:
            crispin_client = CrispinClient(email_address, oauth_token)
            email_address_to_crispins[email_address] = crispin_client
        except Exception, e:
            raise e


        if email_address in user_email_to_token:
            log.info("Replacing oauth token for user %s" % email_address)

        user_email_to_token[email_address] = oauth_token

        # after auth
        session_uuid = str(uuid.uuid1())
        session_to_user[session_uuid] = user
        self.set_secure_cookie("session", session_uuid)

        self.write("<script type='text/javascript'>parent.close();</script>")  # closes window
        self.flush()
        self.finish()

    def fail(self):
        self.write("There was an error authenticating with Google.")
        self.flush()
        log.error("Auth failed")
        raise tornado.web.HTTPError(500, "Google auth failed")
        self.finish()
        return




class LogoutHandler(BaseHandler):
    def get(self):
        self.clear_cookie("session")
        self.redirect("/")



class AngularStaticFileHandler(tornado.web.StaticFileHandler):

    def get(self, path, **kwargs):
        # If not authenticated, redirect home.
        if not self.get_secure_cookie("session"):
            self.redirect(self.settings['login_url'])
            return

        super(AngularStaticFileHandler, self).get(path, **kwargs)

    
    # Don't cache anything right now -- DEBUG
    def set_extra_headers(self, path):
        self.set_header("Cache-control", "no-cache")


class AppRedirectHandler(BaseHandler):
    # TODO put authentication stuff here
    def get(self):
        self.redirect('/app/')


class FileDownloadHandler(BaseHandler):
    def get(self):

        args = self.request.arguments

        uid = args['uid'][0]
        section_index = args['section_index'][0]
        content_type = args['content_type'][0]
        encoding = args['encoding'][0]
        filename = args['filename'][0]

        self.set_header ('Content-Type', content_type)
        self.set_header ('Content-Disposition', 'attachment; filename=' + filename)


        # TODO Some notes about base64 downloading:

        # Some b64 messages may have other additonal encodings
        # Some example strings:

        #     '=?Windows-1251?B?ICLRLcvu5Obo8fLo6iI?=',
        #     '=?koi8-r?B?5tLPzM/XwSDtwdLJzsEg98nUwczYxdfOwQ?=',
        #     '=?Windows-1251?B?1PDu6+7i4CDM4PDo7eAgwujy4Ov85eLt4A?='

        # In these situations, we should split by '?' and then grab the encoding

        # def decodeStr(s):
        #     s = s.split('?')
        #     enc = s[1]
        #     dat = s[3]
        #     return (dat+'===').decode('base-64').decode(enc)

        # The reason for the '===' is that base64 works by regrouping bits; it turns 
        # 3 8-bit chars into 4 6-bit chars (then refills the empty top bits with 0s). 
        # To reverse this, it expects 4 chars at a time - the length of your string 
        # must be a multiple of 4 characters. The '=' chars are recognized as padding; 
        # three chars of padding is enough to make any string a multiple of 4 chars long


        data = crispin_client.fetch_msg_body(uid, section_index, folder='Inbox', )
       
        try:
            if encoding.lower() == 'quoted-printable':
                log.info("Decoded Quoted-Printable")
                data = quopri.decodestring(data)
            elif encoding.lower() == '7bit':
                pass  # This is just ASCII. Do nothing.
            elif encoding.lower() == 'base64':
                log.info("Decoded Base-64")
                data = data.decode('base-64')
            else:
                log.error("Unknown encoding scheme:" + str(encoding))
        except Exception, e:
            print 'Encoding not provided...'

        self.write(data)



# Websocket
class WireConnection(SocketConnection):

    clients = set()

    def on_open(self, request):

        # print request  ConnectionInfo

        # print 'IP:', request.ip
        # # print 'Cookies:', type(request.cookies)
        # print 'user_json:', request.cookies['user'].value
        # print 'Args:', request.arguments


        # global app
        # s = SecureCookieSerializer(app.settings["cookie_secret"])


        # des = s.deserialize('user', request.cookies['user'].value)

        # print 'deserialized:', des

        # Do some auth here
        # self.user_id = request.get_argument('id', None)

        # `request`
        #     ``ConnectionInfo`` object which contains caller IP address, query string
        #     parameters and cookies associated with this request.


        # if not self.user_id:
        #     return False
        log.info("Web client connected.")
        self.clients.add(self)


    def on_close(self):
        log.info("Client disconnected")
        self.clients.remove(self)


    def on_message(self, message):
        console.log("Socket msg: %s", message)


    @event
    def load_messages_for_folder(self, **kwargs):

        folder_name = "Inbox"
        try:

            email_address = 'mgrinich@gmail.com'
            if email_address in email_address_to_crispins:
                crispin_client = email_address_to_crispins[email_address]
            else:
                access_token = user_email_to_token[email_address] 
                crispin_client = CrispinClient(email_address, access_token)


            print 'fetching threads...'
            threads = crispin_client.fetch_messages(folder_name)
            self.emit('load_messages_for_folder_ack', [m.toJSON() for m in threads] )

        except AuthenticationError, e:
            log.error("Couldn't authenticate with credentials.")




    @event
    def load_message_body_with_uid(self, **kwargs):
        assert 'uid' in kwargs
        assert 'section_index' in kwargs

        msg_data = crispin_client.fetch_msg_body(kwargs['uid'], 
                                                 kwargs['section_index'],
                                                 folder='Inbox', )

        content_type = kwargs['content_type']
       
        import webify
        import quopri
        import bleach
        from bs4 import BeautifulSoup


        # Let's decode...
 
        # try:
        #     if encoding.lower() == 'quoted-printable':
        #         log.info("Decoded Quoted-Printable")
        #         data = quopri.decodestring(data)
        #     elif encoding.lower() == '7bit':
        #         pass  # This is just ASCII. Do nothing.
        #     elif encoding.lower() == 'base64':
        #         log.info("Decoded Base-64")
        #         data = data.decode('base-64')
        #     else:
        #         log.error("Unknown encoding scheme:" + str(encoding))
        # except Exception, e:
        #     print 'ENcoding not provided...'


        encoding = kwargs['encoding']
        if encoding.lower() == 'quoted-printable': 
            log.info("Decoded Quoted-Printable")
            msg_data = quopri.decodestring(msg_data)

        elif encoding.lower() == '7bit':
            # This is just ASCII. Do nothing.
            pass
        else:
            log.error("Couldn't figure out how to decode this:" + str(encoding))


        if content_type == 'text/plain':
            msg_data = webify.plaintext2html(msg_data)

        elif content_type == 'text/html':

            soup = BeautifulSoup(msg_data)

            # Bad elements
            for s in soup('head'): s.extract()
            for s in soup('style'): s.extract()
            for s in soup('script'): s.extract()
            for m in soup('html'): m.replaceWithChildren()
            for m in soup('body'): m.replaceWithChildren()

            # for match in soup.findAll('body'):
            #     print 'MATCHED!'
            #     match.replaceWithChildren()
            #     # new_tag = soup.new_tag('div')
            #     # new_tag.contents = b.contents
            #     # b.replace_with(new_tag)

            msg_data = str(soup)


            # msg_data = tornado.escape.linkify(msg_data, shorten=True)

        msg_data = bleach.linkify(msg_data)
        # msg_data = bleach.clean(msg_data, strip=True)
        # msg_data = webify.fix_links(msg_data)

        # Shorten URLs to 30 characters
        soup = BeautifulSoup(msg_data)
        for a in soup.findAll('a'):
            a['target'] = "_blank"
            try:
                if a.contents[0] == a['href']:
                    a.string = a['href'][:30] + '&hellip;'
                a['title'] = a['href']
            except Exception, e:
                log.info("Found anchor without href. Contents: %s" % a)
                pass
        msg_data = str(soup)

        self.emit('load_message_body_with_uid_ack', msg_data )




    @event
    def load_messages_for_thread_id(self, **kwargs):
        if not 'thread_id' in kwargs:
            log.error("Call to get_thread without thread_id")
            return
        thread_id = kwargs['thread_id']
        log.info("Fetching thread id: %s" % thread_id)



        email_address = 'mgrinich@gmail.com'
        if email_address in email_address_to_crispins:
            crispin_client = email_address_to_crispins[email_address]
        else:
            access_token = user_email_to_token[email_address] 
            crispin_client = CrispinClient(email_address, access_token)


        crispin_client.select_allmail_folder()

        messages = crispin_client.fetch_messages_for_thread(thread_id)
        log.info("Returning messages: " + str(messages));
        self.emit('load_messages_for_thread_id_ack', [m.toJSON() for m in messages] )


    def send_message_notification(self):
        log.info("Emitting notification")
        self.emit('new_mail_notification', ['somemessagedata'])



def idler_callback():
    log.info("Received idler callback.")

    for connection in WireConnection.clients:
        connection.send_message_notification()


def startserver(port):

    global app
    app = Application()
    app.listen(port)


    tornado.log.enable_pretty_logging()
    tornado.autoreload.start()
    tornado.autoreload.add_reload_hook(stopsubmodules)


    global crispin_client
    global idler


    # print 'creating client'
    # crispin_client = CrispinClient(OAUTH_ACCOUNT, OAUTH_TOKEN)

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

    for c in email_address_to_crispins.values():
        c.stop()


def stopserver():
    stopsubmodules()
    # Kill IO loop next iteration
    log.info("Stopping Tornado")
    ioloop = tornado.ioloop.IOLoop.instance()
    ioloop.add_callback(ioloop.stop)
