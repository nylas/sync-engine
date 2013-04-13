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
            (r"/", MessagePageHandler),
            (r"/message_raw", MessageRawHandler),
            (r"/mailbox", MailboxHandler)
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
            crispin.setup()
        except Exception, e:
            self.send_error(500)
            raise e

        uid = crispin.latest_message_uid()
        msg = crispin.fetch_msg(uid)

        page_width = self.get_argument("page_width", '600')
        page_width = int(page_width)

        self.render("thread.html",
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
        crispin.setup()
        uid = crispin.latest_message_uid()
        msg = crispin.fetch_msg(uid)
        latest_message_raw = msg.body_text
        self.render("message.html", 
            raw_msg_data = latest_message_raw)


class MailboxHandler(BaseHandler):
    def get(self):

        folder_name = self.get_argument("folder", default="Inbox", strip=False)
        log.info('Opening folder:' + str(folder_name))
        crispin.setup()
        subjects = crispin.fetch_headers(folder_name)
        self.render("mailbox.html", 
                    subjects = subjects)


def main():
    tornado.options.parse_command_line()
    app = Application()
    app.listen(options.port)

    if (app.settings['debug']):
        tornado.autoreload.start()

    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
