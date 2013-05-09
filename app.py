import tornado.ioloop
import tornado.web
import tornado.template
from tornado.options import define, options
define("port", default=8888, help="run on the given port", type=int)

import os.path as os_path
import logging as log
import email

# static request handler
import os
import datetime
import time
import stat
import mimetypes
from models import *

from crispin import CrispinClient

crispin_client = None

from tornadio2 import SocketConnection, TornadioRouter, SocketServer, event



class BaseHandler(tornado.web.RequestHandler):
    pass



class WireConnection(SocketConnection):
    @event
    def ping(self, **kwargs):
        print 'Got %s from client' % kwargs

        now = datetime.datetime.now()

        self.emit('pong',
                  # client,
                  [now.hour, now.minute, now.second, now.microsecond / 1000])


    @event
    def list_inbox(self, **kwargs):

        folder_name = "Inbox"
        crispin_client.select_folder("Inbox")

        threads = crispin_client.fetch_threads(folder_name)
        threads.sort(key=lambda t: t.most_recent_date, reverse=True)

        ret = []
        for t in threads:
            ret.append(dict(
                        subject = t.subject,
                        thread_id = str(t.thread_id)))

        self.emit('inbox', ret)





    @event
    def get_thread(self, **kwargs):
        if not 'thread_id' in kwargs:
            log.error("Call to get_thread without thread_id")
            self.send_error(500)
            return
        thread_id = kwargs['thread_id']
        log.info("Fetching thread id: %s" % thread_id)
        select_info = crispin_client.select_allmail_folder()
        messages = crispin_client.fetch_messages_for_thread(thread_id)
        encoded = [m.encode() for m in messages]        
        self.emit('messages', encoded)


class Application(tornado.web.Application):
    def __init__(self):

        settings = dict(
            cookie_secret="awehofoiasdfhsadkfnwem42rwfubksfj",
            login_url="/auth/login",
            template_path=os_path.join(os_path.dirname(__file__), "templates"),
            static_path=os_path.join(os_path.dirname(__file__), "static"),
            xsrf_cookies=True,
            debug=True,

            flash_policy_port = 843,
            flash_policy_file = os_path.join(os_path.dirname(__file__), "flashpolicy.xml"),
            socket_io_port = 8001
        )


        PingRouter = TornadioRouter(WireConnection, namespace='wire')

        handlers = PingRouter.apply_routes([

            (r'/app/(.*)', tornado.web.StaticFileHandler, {'path': os_path.join(os_path.dirname(__file__), "angular"), 
                                           'default_filename':'index.html'}),
            
            (r'/(?!wire)(.*)', tornado.web.StaticFileHandler, {'path': os_path.join(os_path.dirname(__file__), "static"), 
                                           'default_filename':'index.html'}),



            # (r"/(apple-touch-icon\.png)", tornado.web.StaticFileHandler,
            # (r"/(apple-touch-icon\.png)", tornado.web.StaticFileHandler,
            # (r'/(.*)', tornado.web.StaticFileHandler, {'path': os_path.join(os_path.dirname(__file__), "static"), 'default_filename':''}),
        
        ])

        tornado.web.Application.__init__(self, handlers, **settings)


# Create tornadio router

# # Create socket application
# application = web.Application(
#     PingRouter.apply_routes(
#                            ]),
# )



def main():
    tornado.options.parse_command_line()
    app = Application()
    app.listen(options.port)

    global crispin_client
    crispin_client = CrispinClient()

    if (app.settings['debug']):
        tornado.autoreload.start()

    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
