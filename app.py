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


class MainHandler(BaseHandler):

    def get(self):
        loader = tornado.template.Loader("templates/")
        home_template = loader.load("base.html")
        self.write(home_template.generate(emails=[]))


class MessagePageHandler(BaseHandler):

    def get(self):
        try:
            crispin_client.select_folder("Inbox")
        except Exception, e:
            self.send_error(500)
            raise e

        uid = crispin_client.latest_message_uid()
        msg = crispin_client.fetch_msg(uid)

        page_width = self.get_argument("page_width", '600')
        page_width = int(page_width)

        self.render("singlethread.html",
                    to_name = msg.to_contacts[0]['name'],
                    to_addr = msg.to_contacts[0]['address'],
                    from_name = msg.from_contacts[0]['name'], 
                    from_addr = msg.from_contacts[0]['address'],
                    sent_time = msg.date.strftime('%b %m, %Y &mdash; %I:%M %p'),
                    subject = msg.subject,
                    headers = [],
                    sender_gravatar_url = msg.gravatar() )


class MessageRawHandler(BaseHandler):
    def get(self):
        crispin_client.select_allmail_folder() # anywhere

        msg_id = self.get_argument("msg_id", default=None, strip=False)

        if not msg_id:
            msg_id = crispin_client.latest_message_uid()
            log.warning("No msg_id passed in. Using latest message id: %s" % msg_id)
        else:
            log.info("Passed in msg_id %s", msg_id)
        
        msg = crispin_client.fetch_msg(msg_id)

        latest_message_raw = msg.body_text
        self.render("message.html", 
            raw_msg_data = latest_message_raw)



class MailboxHandler(BaseHandler):
    def get(self):
        """ Takes 'folder' as a query parameter """ 
        folder_name = self.get_argument("folder", default="Inbox", strip=False)        
        crispin_client.select_folder(folder_name)

        threads = crispin_client.fetch_threads(folder_name)
        threads.sort(key=lambda t: t.most_recent_date, reverse=True)

        self.render("mailbox.html", 
                    threads = threads)




import json

class MailboxJSONHandler(BaseHandler):
    def get(self):


        folder_name = self.get_argument("folder", default="Inbox", strip=False)
        log.info('Opening folder:' + str(folder_name))
        
        crispin_client.select_folder("Inbox")

        threads = crispin_client.fetch_threads(folder_name)
        threads.sort(key=lambda t: t.most_recent_date, reverse=True)

        ret = []
        for t in threads:
            ret.append(dict(
                        subject = t.subject,
                        thread_id = t.thread_id))

        self.write( tornado.escape.json_encode(ret) ) 



class MessageThreadHandler(BaseHandler):
    def get(self):

        thread_id = self.get_argument("thread_id", default=None, strip=False)
        if not thread_id:
            self.send_error(500)
            return

        select_info = crispin_client.select_allmail_folder()
        msg_ids = crispin_client.fetch_thread(thread_id)

        log.info("selected thread_id: %s which has msg_ids: %s" % (thread_id, msg_ids) )

        self.render("thread.html", 
            thread_ids = msg_ids)




class WireConnection(SocketConnection):
    @event
    def ping(self, **kwargs):
        print 'Got %s from client' % kwargs

        now = datetime.datetime.now()

        self.emit('pong',
                  # client,
                  [now.hour, now.minute, now.second, now.microsecond / 1000])



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

            (r"/mailbox", MailboxHandler),
            (r"/mailbox_json", MailboxJSONHandler),
            (r"/thread", MessageThreadHandler),
            (r"/message", MessagePageHandler),
            (r"/message_raw", MessageRawHandler),
            
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
