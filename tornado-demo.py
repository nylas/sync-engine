import tornado.ioloop
import tornado.web
import tornado.template

import oauth2 as oauth
import oauth2.clients.imap as imaplib
import email


class MainHandler(tornado.web.RequestHandler):
    def get(self):

        # Get oauth keys:
        # python xoauth.py --generate_oauth_token --user=testing.oauth.1@gmail.com


        # Enter verification code: HNYJNhY2rBCMg0pA1grbyaK2
        # oauth_token: 1/LG4tUierWCflZoMoBk8nL7Kev7mITub9-bAVXAJlDIc
        # oauth_token_secret: 2Jh36SZR39MSChO9OVD2b7vV

        # Set up your Consumer and Token as per usual. Just like any other
        # three-legged OAuth request.
        consumer = oauth.Consumer('anonymous', 'anonymous')
        token = oauth.Token('1/LG4tUierWCflZoMoBk8nL7Kev7mITub9-bAVXAJlDIc', 
            '2Jh36SZR39MSChO9OVD2b7vV')
        account = 'mgrinich@gmail.com'

        # Setup the URL according to Google's XOAUTH implementation. Be sure
        # to replace the email here with the appropriate email address that
        # you wish to access.
        url = "https://mail.google.com/mail/b/" + account + "/imap/"

        conn = imaplib.IMAP4_SSL('imap.googlemail.com')

        conn.debug = 4 

        # This is the only thing in the API for impaplib.IMAP4_SSL that has 
        # changed. You now authenticate with the URL, consumer, and token.
        conn.authenticate(url, consumer, token)

        # Once authenticated everything from the impalib.IMAP4_SSL class will 
        # work as per usual without any modification to your code.
        conn.select('Inbox')


        raw_mailboxes = conn.list()[1]


        my_mailboxes = [box.split(' "/" ')[1][1:-1] for box in raw_mailboxes]

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

        print my_mailboxes

        self.write( home_template.generate(emails=my_mailboxes))


class MailboxHandler(tornado.web.RequestHandler):
    def get(self):


        print 'looking for mailbox'
        mailbox_tofetch = self.get_argument("mailbox_name")

        print 'passed in ', mailbox_tofetch

        consumer = oauth.Consumer('anonymous', 'anonymous')
        token = oauth.Token('1/LG4tUierWCflZoMoBk8nL7Kev7mITub9-bAVXAJlDIc', 
            '2Jh36SZR39MSChO9OVD2b7vV')
        account = 'mgrinich@gmail.com'


        url = "https://mail.google.com/mail/b/" + account + "/imap/"
        conn = imaplib.IMAP4_SSL('imap.googlemail.com')
        conn.debug = 4

        conn.authenticate(url, consumer, token)

        # Once authenticated everything from the impalib.IMAP4_SSL class will 
        # work as per usual without any modification to your code.
        conn.select(mailbox_tofetch)

        status, data = conn.uid('fetch',uid, 'RFC822')

        raw_mailboxes = conn.list()[1]


        my_mailboxes = [box.split(' "/" ')[1][1:-1] for box in raw_mailboxes]

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

        print my_mailboxes

        self.write()


application = tornado.web.Application([
    (r"/", MainHandler),
    (r"/mailbox", MailboxHandler),
], debug=True)


if __name__ == "__main__":
    application.listen(8888)
    tornado.ioloop.IOLoop.instance().start()
