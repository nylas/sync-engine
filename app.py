import tornado.ioloop
import tornado.web
import tornado.template
from tornado.options import define, options
define("port", default=8888, help="run on the given port", type=int)

import os.path as os_path
import logging as log

import crispin


class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", MailboxHandler),
            (r"/mailbox", MailboxHandler),
            (r"/thread", MessageThreadHandler),
            (r"/message", MessagePageHandler),
            (r"/message_raw", MessageRawHandler),
            # (r"/(apple-touch-icon\.png)", tornado.web.StaticFileHandler,
            # (r"/(apple-touch-icon\.png)", tornado.web.StaticFileHandler,
        ]
        settings = dict(
            cookie_secret="awehofoiasdfhsadkfnwem42rwfubksfj",
            login_url="/auth/login",
            template_path=os_path.join(os_path.dirname(__file__), "templates"),
            static_path=os_path.join(os_path.dirname(__file__), "static"),
            xsrf_cookies=True,
            debug=True,
        )
        tornado.web.Application.__init__(self, handlers, **settings)


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
            crispin.connect()
            crispin.select_folder("Inbox")
        except Exception, e:
            self.send_error(500)
            raise e

        uid = crispin.latest_message_uid()
        msg = crispin.fetch_msg(uid)

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
        crispin.connect()
        crispin.select_folder("Inbox")

        msg_id = self.get_argument("msg_id", default=None, strip=False)

        if not msg_id:
            msg_id = crispin.latest_message_uid()
            log.warning("No msg_id passed in. Using latest message id: %s" % msg_id)
        else:
            log.info("Passed in msg_id %s", msg_id)
        
        msg = crispin.fetch_msg(msg_id)

        latest_message_raw = msg.body_text
        self.render("message.html", 
            raw_msg_data = latest_message_raw)



class MailboxHandler(BaseHandler):
    def get(self):

        folder_name = self.get_argument("folder", default="Inbox", strip=False)
        log.info('Opening folder:' + str(folder_name))
        
        # Todo: Do this for every setup somehow.
        if not(crispin.connect()):
            log.error("Couldn't connect. Proably offline right now.")
            self.send_error(500)
            return

        crispin.select_folder("Inbox")

        new_messages = crispin.fetch_headers(folder_name)

        subjs = []
        for m in new_messages:
            s = m.trimmed_subject()
            if not s in subjs:
                subjs.append(s)

        self.render("mailbox.html", 
                    subjects = subjs,
                    messages = new_messages)



class MessageThreadHandler(BaseHandler):
    def get(self):

        thread_id = self.get_argument("thread_id", default=None, strip=False)
        if not thread_id:
            self.send_error(500)
            return

        crispin.connect()
        crispin.select_folder("Inbox")

        msg_ids = crispin.fetch_thread(thread_id)

        log.info("selected thread_id: %s which has msg_ids: %s" % (thread_id, msg_ids) )

        self.render("thread.html", 
            thread_ids = msg_ids)

        


def main():
    tornado.options.parse_command_line()
    app = Application()
    app.listen(options.port)

    if (app.settings['debug']):
        tornado.autoreload.start()

    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
