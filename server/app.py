import tornado.ioloop
import tornado.web
import tornado.template
import tornado.log
import tornado.options
import tornado.gen
import tornado.escape
from tornadio2 import SocketConnection, TornadioRouter, event

import tornadio2.gen

import os.path as os_path
import logging as log

from models import *

from crispin import CrispinClient
from idler import Idler

from concurrent.futures import ThreadPoolExecutor
from functools import partial, wraps

crispin_client = None
EXECUTOR = ThreadPoolExecutor(max_workers=20)


import oauth2


PATH_TO_ANGULAR = os_path.join(os_path.dirname(__file__), "../angular")
PATH_TO_STATIC = os_path.join(os_path.dirname(__file__), "../static")


class Application(tornado.web.Application):
    def __init__(self):

        settings = dict(

            static_path=os_path.join(PATH_TO_STATIC),
            xsrf_cookies=True,
            debug=True,
            flash_policy_port = 843,
            flash_policy_file = os_path.join(PATH_TO_STATIC + "/flashpolicy.xml"),
            socket_io_port = 8001,



            cookie_secret="32oETzKXQAGaYdkL5gEmGeJJFuYh7EQnp2XdTP1o/Vo=",
            login_url="/auth/login",
            redirect_uri="http://localhost:8888/auth/login",

            google_consumer_key="786647191490.apps.googleusercontent.com",  # client ID
            google_consumer_secret="0MnVfEYfFebShe9576RR8MCK",  # aka client secret



        )

        PingRouter = TornadioRouter(WireConnection, namespace='wire')
        
        handlers = PingRouter.apply_routes([
            (r"/", MainHandler),
            (r"/auth/login", AuthHandler),
            (r"/auth/logout", LogoutHandler),
            (r'/app/(.*)', NoCacheStaticFileHandler, {'path': PATH_TO_ANGULAR, 
                                           'default_filename':'index.html'}),
            (r'/app', AppRedirectHandler),
            (r'/download_file', FileDownloadHandler),
            # /wire is the route for messages.
            (r'/(?!wire|!app|download_file)(.*)', tornado.web.StaticFileHandler, {'path': PATH_TO_STATIC, 
                                           'default_filename':'index.html'}),       
        ])

        tornado.web.Application.__init__(self, handlers, **settings)




class BaseHandler(tornado.web.RequestHandler):
    # TODO put authentication stuff here
    def get_current_user(self):
        user_json = self.get_secure_cookie("user")
        if not user_json: return None
        return tornado.escape.json_decode(user_json)


class MainHandler(BaseHandler):
    # @tornado.web.authenticated
    def get(self):

        if self.current_user:
            name = tornado.escape.xhtml_escape(self.current_user["name"])
            self.write("Hello, " + name)
            self.write("<br><br><a href=\"/auth/logout\">Log out</a>")
        else:
            self.write("Go ahead and <a href=\"/auth/login\">login</a>")



class AuthHandler(BaseHandler, oauth2.GoogleOAuth2Mixin):
    @tornado.web.asynchronous
    def get(self):
        if self.get_argument("code", None):
            authorization_code = self.get_argument("code", None)
            self.get_authenticated_user(authorization_code, self.async_callback(self._on_auth))
            return
        self.authorize_redirect()
    
    def _on_auth(self, response):
        print 'RESPONSE:', response
        # print response.body
        # print response.request.headers
        # if response.error:
        #     raise tornado.web.HTTPError(500, "Google auth failed")

        user = response.read()
        print user


        global crispin_client
        global idler

        crispin_client = CrispinClient('mgrinich@gmail.com', oauth2.GoogleOAuth2Mixin.access_token)

        # idler = Idler(ioloop=loop,
        #               event_callback=idler_callback,
        #               # folder=crispin_client.all_mail_folder_name())
        #               folder="Inbox")
        # idler.connect()
        # idler.idle()



        # self.set_secure_cookie("user", tornado.escape.json_encode(user))
        self.set_secure_cookie("user", user)
        self.redirect("/")


class LogoutHandler(BaseHandler):
    def get(self):
        self.clear_cookie("user")
        self.redirect("/")




class NoCacheStaticFileHandler(tornado.web.StaticFileHandler):
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



# Global, ugh.
def dontblock(fn_to_call, *args, **kwargs):
    callback = kwargs.pop('callback', None)

    EXECUTOR.submit(
        partial(fn_to_call, *args, **kwargs)
    ).add_done_callback(
        lambda future: tornado.ioloop.IOLoop.instance().add_callback(
            partial(callback, future)))


class WireConnection(SocketConnection):
    """
    This is the basic mechanism we use to send messages
    to the client over websockets.
    """

    clients = set()

    def on_open(self, request):

        # Do some auth here
        # self.user_id = request.get_argument('id', None)

        # if not self.user_id:
        #     return False
        log.info("Web client connected.")
        self.clients.add(self)


    def on_close(self):
        log.info("Client disconnected")
        self.clients.remove(self)


    def on_message(self, message):
        console.log("Socket msg: %s", message)


    # Uncomment this and the call to yield tornado.gen.xxxxx to use multithreaded stuff
    # @tornado.gen.engine
    # def on_event(self, name, *args, **kwargs):
    #     """Wrapped ``on_event`` handler, which will queue events and will allow usage
    #     of the ``yield`` in the event handlers.

    #     If you want to use non-queued version, just wrap ``on_event`` with ``gen.engine``.
    #     """
    #     return super(WireConnection, self).on_event(name, *args, **kwargs)


    @event
    def load_messages_for_folder(self, **kwargs):

        # Must say dontblock, then function name, then args
        # future = yield tornado.gen.Task(dontblock, self.expensive_load_threads, 'Inbox')
        # threads = future.result()

        messages = self.expensive_load_threads('Inbox')
        self.emit('load_messages_for_folder_ack', [m.toJSON() for m in messages] )


    def expensive_load_threads(self, folder_name):
        folder_name = "Inbox"
        # TODO maybe create a new client to make things thread safe?
        # newclient = CrispinClient()
        # crispin_client.select_folder("Inbox")
        # UIDs = crispin_client.fetch_all_udids()
        # msgs = crispin_client.fetch_headers_for_uids(folder_name, UIDs)

        threads = crispin_client.fetch_messages(folder_name)
        return threads


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

    app = Application()
    app.listen(port)


    tornado.log.enable_pretty_logging()
    tornado.autoreload.start()
    tornado.autoreload.add_reload_hook(stopsubmodules)

    loop = tornado.ioloop.IOLoop.instance()


    loop.start()


def stopsubmodules():
    if idler: 
        idler.stop()
    if crispin_client:
        crispin_client.stop()


def stopserver():
    stopsubmodules()
    # Kill IO loop next iteration
    log.info("Stopping tornado")
    ioloop = tornado.ioloop.IOLoop.instance()
    ioloop.add_callback(ioloop.stop)
