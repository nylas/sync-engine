import tornado.ioloop
import tornado.web
import tornado.template
from tornado.options import define, options
define("port", default=8888, help="run on the given port", type=int)

import os.path as os_path
import logging as log

# static request handler
import os
import datetime
import stat
import mimetypes

from crispin import CrispinClient

crispin_client = None


class Application(tornado.web.Application):
    def __init__(self):

        settings = dict(
            cookie_secret="awehofoiasdfhsadkfnwem42rwfubksfj",
            login_url="/auth/login",
            template_path=os_path.join(os_path.dirname(__file__), "templates"),
            static_path=os_path.join(os_path.dirname(__file__), "static"),
            xsrf_cookies=True,
            debug=True,
        )

        handlers = [
            (r'/app/(.*)', AppStaticFileHandler),
            (r"/mailbox", MailboxHandler),
            (r"/mailbox_json", MailboxJSONHandler),
            (r"/thread", MessageThreadHandler),
            (r"/message", MessagePageHandler),
            (r"/message_raw", MessageRawHandler),
            # (r"/(apple-touch-icon\.png)", tornado.web.StaticFileHandler,
            # (r"/(apple-touch-icon\.png)", tornado.web.StaticFileHandler,
            (r'/(.*)', tornado.web.StaticFileHandler, {'path': os_path.join(os_path.dirname(__file__), "static"), 'default_filename':'index.html'}),
        ]

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

        


class AppStaticFileHandler(tornado.web.RequestHandler):
    """A simple handler that can serve static content from a directory.
 
    To map a path to this handler for a static data directory /var/www,
    you would add a line to your application like:
 
        application = web.Application([
            (r"/static/(.*)", web.StaticFileHandler, {"path": "/var/www"}),
        ])
 
    The local root directory of the content should be passed as the "path"
    argument to the handler.
 
    To support aggressive browser caching, if the argument "v" is given
    with the path, we set an infinite HTTP expiration header. So, if you
    want browsers to cache a file indefinitely, send them to, e.g.,
    /static/images/myimage.png?v=xxx.
    """
    def initialize(**kwargs):
        
        path = os_path.join(os_path.dirname(__file__), "angular")
        default_filename = 'index.html'
        self.root = os.path.abspath(path) + os.path.sep
        self.default_filename = default_filename
 
    def head(self, path):
        self.get(path, include_body=False)
 
    def get(self, path, include_body=True):
        if os.path.sep != "/":
            path = path.replace("/", os.path.sep)
        abspath = os.path.abspath(os.path.join(self.root, path))
        # os.path.abspath strips a trailing /
        # it needs to be temporarily added back for requests to root/
        if not (abspath + os.path.sep).startswith(self.root):
            raise HTTPError(403, "%s is not in root static directory", path)
        if os.path.isdir(abspath) and self.default_filename is not None:
            # need to look at the request.path here for when path is empty
            # but there is some prefix to the path that was already
            # trimmed by the routing
            if not self.request.path.endswith("/"):
                self.redirect(self.request.path + "/")
                return
            abspath = os.path.join(abspath, self.default_filename)
        if not os.path.exists(abspath):
            raise HTTPError(404)
        if not os.path.isfile(abspath):
            raise HTTPError(403, "%s is not a file", path)
 
        stat_result = os.stat(abspath)
        modified = datetime.datetime.fromtimestamp(stat_result[stat.ST_MTIME])
 
        self.set_header("Last-Modified", modified)
        if "v" in self.request.arguments:
            self.set_header("Expires", datetime.datetime.utcnow() + \
                                       datetime.timedelta(days=365*10))
            self.set_header("Cache-Control", "max-age=" + str(86400*365*10))
        else:
            self.set_header("Cache-Control", "public")
        mime_type, encoding = mimetypes.guess_type(abspath)
        if mime_type:
            self.set_header("Content-Type", mime_type)
 
        self.set_extra_headers(path)
 
        # Check the If-Modified-Since, and don't send the result if the
        # content has not been modified
        ims_value = self.request.headers.get("If-Modified-Since")
        if ims_value is not None:
            date_tuple = email.utils.parsedate(ims_value)
            if_since = datetime.datetime.fromtimestamp(time.mktime(date_tuple))
            if if_since >= modified:
                self.set_status(304)
                return
 
        if not include_body:
            return
        file = open(abspath, "rb")
        try:
            self.write(file.read())
        finally:
            file.close()
 
    def set_extra_headers(self, path):
        """For subclass to add extra headers to the response"""
        pass





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
