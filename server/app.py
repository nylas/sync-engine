import tornado.ioloop
import tornado.web
import tornado.template
import tornado.log
import tornado.options
from tornadio2 import SocketConnection, TornadioRouter, event

import os.path as os_path
import logging as log

from models import *

from crispin import CrispinClient
from idler import Idler


crispin_client = None


PATH_TO_ANGULAR = os_path.join(os_path.dirname(__file__), "../angular")
PATH_TO_STATIC = os_path.join(os_path.dirname(__file__), "../static")


class Application(tornado.web.Application):
    def __init__(self):

        settings = dict(
            cookie_secret="awehofoiasdfhsadkfnwem42rwfubksfj",
            login_url="/auth/login",
            static_path=os_path.join(PATH_TO_STATIC),
            xsrf_cookies=True,
            debug=True,
            flash_policy_port = 843,
            flash_policy_file = os_path.join(PATH_TO_STATIC + "/flashpolicy.xml"),
            socket_io_port = 8001
        )

        PingRouter = TornadioRouter(WireConnection, namespace='wire')
        
        handlers = PingRouter.apply_routes([

            (r'/app/(.*)', tornado.web.StaticFileHandler, {'path': PATH_TO_ANGULAR, 
                                           'default_filename':'index.html'}),
            (r'/app', AppRedirectHandler),
            # /wire is the route for messages.
            (r'/(?!wire|!app)(.*)', tornado.web.StaticFileHandler, {'path': PATH_TO_STATIC, 
                                           'default_filename':'index.html'}),        
        ])

        tornado.web.Application.__init__(self, handlers, **settings)



class AppRedirectHandler(tornado.web.RequestHandler):
    # TODO put authentication stuff here
    def get(self):
        self.redirect('/app/')


class BaseHandler(tornado.web.RequestHandler):
    # TODO put authentication stuff here
    pass



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
        log.info("Client connected.")
        self.clients.add(self)

    def on_close(self):
        log.info("Cient disconnected")
        self.clients.remove(self)


    def on_message(self, message):
        console.log("Socket msg: %s", message)


    @event
    def load_threads_for_folder(self, **kwargs):

        print 'Loading folder.'
        print 'args:', kwargs

        folder_name = "Inbox"
        crispin_client.select_folder("Inbox")

        threads = crispin_client.fetch_threads(folder_name)

        self.emit('load_threads_for_folder_ack', [t.toJSON() for t in threads] )


    @event
    def load_messages_for_thread_id(self, **kwargs):
        if not 'thread_id' in kwargs:
            log.error("Call to get_thread without thread_id")
            self.send_error(500)
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

    global crispin_client
    crispin_client = CrispinClient()

    tornado.log.enable_pretty_logging()
    tornado.autoreload.start()
    tornado.autoreload.add_reload_hook(stopsubmodules)

    loop = tornado.ioloop.IOLoop.instance()
    global idler
    idler = Idler(ioloop=loop, 
                  event_callback=idler_callback, 
                  # folder=crispin_client.all_mail_folder_name())
                  folder="Inbox")

    idler.connect()
    idler.idle()

    loop.start()


def stopsubmodules():
    idler.stop()
    crispin_client.stop()


def stopserver():
    stopsubmodules()
    # Kill IO loop next iteration
    log.info("Stopping tornado")
    ioloop = tornado.ioloop.IOLoop.instance()
    ioloop.add_callback(ioloop.stop)
