import tornado.ioloop
import tornado.web
import tornado.template
import os

from sendreceive import AwesomeMail

from email.Parser import Parser
import string
import time
import unicodedata
import email.utils
import re
from bs4 import BeautifulSoup
import urllib, hashlib


class MainHandler(tornado.web.RequestHandler):
    def get(self):

        loader = tornado.template.Loader("templates/")
        home_template = loader.load("base.html")

        self.write( home_template.generate(emails=[]))

class MessagePageHandler(tornado.web.RequestHandler):
    def get(self):

        # my_mailboxes = [box.split(' "/" ')[1][1:-1] for box in raw_mailboxes]

        am = AwesomeMail()
        am.setup()
        latest_message_raw = am.fetch_latest_message()

        parser = Parser()
        message = parser.parsestr(latest_message_raw)


        tos = message.get_all('to', [])
        ccs = message.get_all('cc', [])
        froms = message.get_all('from', [])

        headers = message.items()

        resent_tos = message.get_all('resent-to', [])
        resent_ccs = message.get_all('resent-cc', [])


        if len(tos[0]) > 0:
            to_name = email.utils.getaddresses(tos)[0][0]
            to_addr = email.utils.getaddresses(tos)[0][1]
        else:
            to_name = "undisclosed recipients"
            to_addr = ""

        if len(froms[0]) > 0:
            from_name = email.utils.getaddresses(froms)[0][0]
            from_addr = email.utils.getaddresses(froms)[0][1]
        else:
            from_name = "Unknown from!"
            from_addr = ""


        subject = message['Subject']


        # from_addr = message["From"]


        # created_time = time.mktime( parse(mail["Date"]).timetuple() ) # no good
        date_tuple = email.utils.parsedate_tz(message["Date"])
        # sent_time_obj = time.mktime( date_tuple[:9]  )
        # sent_time_obj = time.mktime( date_tuple[:9]  )        
        # sent_time = time.strftime("%Y-%m-%d %H:%M:%S", date_tuple[:9])

        sent_time = time.strftime("%b %m, %Y &mdash; %I:%M %p", date_tuple[:9])

        body = None
        content_type = None

        for part in message.walk():
            content_type = part.get_content_type()
            body = part.get_payload(decode=True)

            if content_type == "text/html":
            	break


        # regexes = [ re.compile(r'From:\s*' + re.escape(from_addr), re.IGNORECASE | re.MULTILINE),
        #             re.compile(r'<' + re.escape(from_addr) + r'>', re.IGNORECASE),
        #             re.compile(re.escape(from_addr) + r'\s+wrote:', re.IGNORECASE),
        #             re.compile(r'^.*On.*(\n|\r|\r\n)?wrote:$', re.IGNORECASE),
        #             re.compile(r'-+original\s+message-+\s*$', re.IGNORECASE),
        #             re.compile(r'from:\s*$', re.IGNORECASE)]


        if content_type == "text/plain":
            m = re.search('^.*On\ .*(\n|\r|\r\n)?wrote:(\r)*$', body, re.IGNORECASE | re.MULTILINE)
        elif content_type == "text/html":
            m = re.search('On\ .*(\n|\r|\r\n)?wrote:(\r)*', body, re.IGNORECASE | re.MULTILINE)
        else :
            print 'poop'


        endpoint = len(body)
        if m != None:
            endpoint = m.start()
        body = body[: endpoint]

        # TODO this whitespace trimming should be part of regex
        while body.endswith('\n') or body.endswith('\r'):
            body = body[:-2]
            


        if content_type == 'text/plain':
        	body = plaintext2html(body)

        body = fix_links(body)


        loader = tornado.template.Loader("templates/")
        home_template = loader.load("message.html")


        sender_gravatar_url = gravatar_url(from_addr)

        self.write( home_template.generate(raw_msg_data = body, 
                                            to_name = to_name,
                                            to_addr = to_addr,
                                            from_name = from_name, 
                                            from_addr = from_addr,
                                            content_type = content_type, 
                                            sent_time = sent_time,
                                            subject = subject,
                                            headers = headers,
                                            sender_gravatar_url = sender_gravatar_url))


def gravatar_url(email):

    default = "http://www.example.com/default.jpg"
    size = 25

    # construct the url
    gravatar_url = "http://www.gravatar.com/avatar/" + hashlib.md5(email.lower()).hexdigest() + "?"
    gravatar_url += urllib.urlencode({'d':'mm', 's':str(size)})

    return gravatar_url






import re
import cgi

re_string = re.compile(r'(?P<htmlchars>[<&>])|(?P<space>^[ \t]+)|(?P<lineend>\r\n|\r|\n)|(?P<protocal>(^|\s)((http|ftp)://.*?))(\s|$)', re.S|re.M|re.I)
def plaintext2html(text, tabstop=4):
    def do_sub(m):
        c = m.groupdict()
        if c['htmlchars']:
            return cgi.escape(c['htmlchars'])
        if c['lineend']:
            return '<br/>'
        elif c['space']:
            t = m.group().replace('\t', '&nbsp;'*tabstop)
            t = t.replace(' ', '&nbsp;')
            return t
        elif c['space'] == '\t':
            return ' '*tabstop;
        else:
            url = m.group('protocal')
            if url.startswith(' '):
                prefix = ' '
                url = url[1:]
            else:
                prefix = ''
            last = m.groups()[-1]
            if last in ['\n', '\r', '\r\n']:
                last = '<br/>'
            return '%s<a href="%s">%s</a>%s' % (prefix, url, url, last)
    return re.sub(re_string, do_sub, text)


def fix_links(text):
    soup = BeautifulSoup(text)
    for a in soup.findAll('a'):
        a['target'] = "_blank"

    for b in soup.findAll('body'):
        new_tag = soup.new_tag('div')
        new_tag.contents = b.contents
        b.replace_with(new_tag)
    return str(soup)


class MessageHTMLHandler(tornado.web.RequestHandler):
    def get(self):

        # my_mailboxes = [box.split(' "/" ')[1][1:-1] for box in raw_mailboxes]

        am = AwesomeMail()
        am.setup()
        latest_message_raw = am.fetch_latest_message()

        parser = Parser()
        message = parser.parsestr(latest_message_raw)


        body = None
        content_type = None
        for part in message.walk():

            content_type = part.get_content_type()
            body = part.get_payload(decode=True)

            if content_type == "text/html": break




        if content_type == "text/plain":
            m = re.search('^.*On\ .*(\n|\r|\r\n)?wrote:(\r)*$', body, re.IGNORECASE | re.MULTILINE)
        elif content_type == "text/html":
            m = re.search('On\ .*(\n|\r|\r\n)?wrote:(\r)*', body, re.IGNORECASE | re.MULTILINE)
        else :
            print 'poop'


        endpoint = len(body)


        print body

        if m != None:
            endpoint = m.start()
        body = body[: endpoint-1]

        print {'body', body}

        self.write(body)



class MailboxHandler(tornado.web.RequestHandler):
    def get(self):



        # print 'looking for mailbox'
        # mailbox_tofetch = self.get_argument("mailbox_name")

        # print 'passed in ', mailbox_tofetch

        # consumer = oauth.Consumer('anonymous', 'anonymous')
        # token = oauth.Token('1/LG4tUierWCflZoMoBk8nL7Kev7mITub9-bAVXAJlDIc', 
        #     '2Jh36SZR39MSChO9OVD2b7vV')
        # account = 'mgrinich@gmail.com'


        # url = "https://mail.google.com/mail/b/" + account + "/imap/"
        # conn = imaplib.IMAP4_SSL('imap.googlemail.com')
        # conn.debug = 4

        # conn.authenticate(url, consumer, token)

        # # Once authenticated everything from the impalib.IMAP4_SSL class will 
        # # work as per usual without any modification to your code.
        # conn.select(mailbox_tofetch)

        # status, data = conn.uid('fetch',uid, 'RFC822')

        # raw_mailboxes = conn.list()[1]


        # my_mailboxes = [box.split(' "/" ')[1][1:-1] for box in raw_mailboxes]

        # for i in range(1, 5):
        #     typ, msg_data = conn.fetch(str(i), '(RFC822)')
        #     for response_part in msg_data:
        #         if isinstance(response_part, tuple):
        #             msg = email.message_from_string(response_part[1])
                    
        #             for header in [ 'subject', 'to', 'from' ]:
        #                 hdr =  '%-8s: %s' % (header.upper(), msg[header])
        #                 self.write(hdr)
        #                 self.write("<br/><br/>")


        loader = tornado.template.Loader("/Users/mg/Dropbox/email/")
        home_template = loader.load("base.html")

        self.write()


settings = {
    "static_path": os.path.join(os.path.dirname(__file__), "static"),
    # "cookie_secret": "__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
    # "login_url": "/login",
    # "xsrf_cookies": True,
    "debug": True,
}


application = tornado.web.Application([
    (r"/", MainHandler),
    (r"/message", MessagePageHandler),
    (r"/message_html", MessageHTMLHandler),
        # (r"/(apple-touch-icon\.png)", tornado.web.StaticFileHandler,


    # (r"/mailbox", MailboxHandler),
], **settings)
# ], **settings)

if __name__ == "__main__":
    application.listen(8888)
    tornado.autoreload.start()
    tornado.ioloop.IOLoop.instance().start()
