import tornado.ioloop
import tornado.web
import tornado.template
import os
import logging

import crispin

from email.Parser import Parser
from email.header import decode_header

import string
import time
import unicodedata
import email.utils
import re
from bs4 import BeautifulSoup

from pynliner import Pynliner

from tornado.options import define, options
define("port", default=8888, help="run on the given port", type=int)

from webify import plaintext2html, fix_links, gravatar_url


class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
        (r"/", MessagePageHandler),
        (r"/message_html", MessageHTMLHandler),
        (r"/message_raw", MessageRawHandler),
        (r"/mailbox", MailboxHandler)
            # (r"/(apple-touch-icon\.png)", tornado.web.StaticFileHandler,
                # (r"/(apple-touch-icon\.png)", tornado.web.StaticFileHandler,
        ]
        settings = dict(
            cookie_secret="awehofoiasdfhsadkfnwem42rwfubksfj",
            login_url="/auth/login",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
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
        self.write( home_template.generate(emails=[]))


class MessagePageHandler(BaseHandler):
    def get(self):

        try:
            crispin.setup()
        except Exception, e:
            self.send_error(503, "Gmail is temporarily unavailable.")
            raise e

        latest_message_raw = crispin.fetch_latest_message()

        parser = Parser()
        message = parser.parsestr(latest_message_raw)


        tos = message.get_all('to', [])
        ccs = message.get_all('cc', [])
        froms = message.get_all('from', [])

        headers = message.items()

        resent_tos = message.get_all('resent-to', [])
        resent_ccs = message.get_all('resent-cc', [])

        default_encoding="ascii"


        if len(tos[0]) > 0:
            to_name = email.utils.getaddresses(tos)[0][0]
            to_addr = email.utils.getaddresses(tos)[0][1]
        else:
            to_name = "undisclosed recipients"
            to_addr = ""

        if len(froms[0]) > 0:
            from_name = email.utils.getaddresses(froms)[0][0]

            from_name_decoded = decode_header(from_name)

            from_name_sections = [unicode(text, charset or default_encoding)
                               for text, charset in from_name_decoded]
            from_name = u"".join(from_name_sections)

            from_addr = email.utils.getaddresses(froms)[0][1]
        else:
            from_name = "Unknown from!"
            from_addr = ""


        print 'decoding subject'

        header_text = message['Subject']

        subject_header_decoded = decode_header(header_text)
        header_sections = [unicode(text, charset or default_encoding)
                           for text, charset in subject_header_decoded]
        
        subject = u"".join(header_sections)

        # Headers will wrap when longer than 78 lines per RFC822_2
        subject = subject.replace('\n\t', '')
        subject = subject.replace('\r\n', '')

        if subject[:4] == u'RE: ' or subject[:4] == u'Re: ' :
            subject = subject[4:]


        print 'subject', subject

        # from_addr = message["From"]


        # created_time = time.mktime( parse(mail["Date"]).timetuple() ) # no good
        date_tuple = email.utils.parsedate_tz(message["Date"])
        # sent_time_obj = time.mktime( date_tuple[:9]  )
        # sent_time_obj = time.mktime( date_tuple[:9]  )        
        # sent_time = time.strftime("%Y-%m-%d %H:%M:%S", date_tuple[:9])

        sent_time = time.strftime("%b %m, %Y &mdash; %I:%M %p", date_tuple[:9])

        msg_text = None
        content_type = None

        for part in message.walk():
            content_type = part.get_content_type()
            msg_text = part.get_payload(decode=True)

            if content_type == "text/html":
            	break

            if part.get_content_type() == 'text/plain':
                msg_encoding = part.get_content_charset()

                # TODO check to see if we always have to do this? does it break stuff?
                msg_text = part.get_payload().decode('quoted-printable')
                # break


        # TOFIX I think this is really slow
        # This shit is broken
        # if content_type == "text/html":
        #     body = Pynliner().from_string(body).run()



        # EXTRACT MESSAGE TEXT

        # TODO add signature detection
        #  r'^-{2}\s' or something


        if content_type == "text/plain":
            regexes =  [r'-+original\s+message-+\s*$', 
                        r'^.*On\ .*(\n|\r|\r\n)?wrote:(\r)*$',
                        r'From:\s*' + re.escape(from_addr),
                        r'<' + re.escape(from_addr) + r'>',
                        re.escape(from_addr) + r'\s+wrote:',
                        r'from:\s*$']

        elif content_type == "text/html":
            regexes =  [r'-+original\s+message-+\s*', 
                        r'^.*On\ .*(\n|\r|\r\n)?wrote:(\r)*$']
                        # r'On\ .*(\n|\r|\r\n)?wrote:(\r)*']
        else :
            print 'poop'



        endpoint = len(msg_text) # long email

        for r in regexes:
            m = re.search(r, msg_text, re.IGNORECASE | re.MULTILINE)
            if m == None: continue
            e = m.start()
            if m.start() < endpoint :
                endpoint = e

        msg_text = msg_text[: endpoint]

        # TODO this whitespace trimming should be part of regex
        while msg_text.endswith('\n') or msg_text.endswith('\r'):
            msg_text = msg_text[:-2]
            


        if content_type == 'text/plain':
        	msg_text = plaintext2html(msg_text)


        try:
            msg_text = fix_links(msg_text)
        except Exception, e:
            pass
            # TOFIX actually raise e
        

        sender_gravatar_url = gravatar_url(from_addr)

        page_width = self.get_argument("page_width", '600')
        page_width = int(page_width)


        self.render("message.html", 
                    raw_msg_data = msg_text, 
                    to_name = to_name,
                    to_addr = to_addr,
                    from_name = from_name, 
                    from_addr = from_addr,
                    content_type = content_type, 
                    sent_time = sent_time,
                    subject = subject,
                    headers = headers,
                    sender_gravatar_url = sender_gravatar_url)


class MessageHTMLHandler(BaseHandler):
    def get(self):

        # my_mailboxes = [box.split(' "/" ')[1][1:-1] for box in raw_mailboxes]

        crispin.setup()
        latest_message_raw = crispin.fetch_latest_message()

        parser = Parser()
        message = parser.parsestr(latest_message_raw)


        body = None
        content_type = None
        for part in message.walk():

            content_type = part.get_content_type()
            body = part.get_payload(decode=True)

            if content_type == "text/html": break


        self.write(body)



class MessageRawHandler(BaseHandler):
    def get(self):

        msgid = self.get_argument("msgid", default="")
        crispin.setup()

        latest_message_raw = crispin.fetch_msg(0)
        self.write(latest_message_raw)


class MailboxHandler(BaseHandler):
    def get(self):

        folder_name = self.get_argument("folder", default="Inbox", strip=False)
        logging.info('Opening folder:' + str(folder_name))

        crispin.setup()
        subjects = crispin.fetch_headers(folder_name)

        self.render("mailbox.html", 
                    subjects = subjects)




def main():
    tornado.options.parse_command_line()
    app = Application()
    app.listen(options.port)

    if ( app.settings['debug'] ):
        tornado.autoreload.start()

    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
