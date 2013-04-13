# For sending mail

import oauth2.clients.smtp as smtplib
import oauth2 as oauth

import logging as log
import auth


class SMTP(object):

    def __init__(self):
        self.conn = None

    def setup(self):
        # self.conn = smtplib.SMTP('smtp.googlemail.com', 587)
        self.conn = smtplib.SMTP(auth.SMTP_HOST, 587)

        #conn.debug = 4 
        self.conn.set_debuglevel(True)
        self.conn.ehlo()
        self.conn.starttls()
        self.conn.ehlo()

        consumer = oauth.Consumer(auth.CONSUMER_KEY, auth.CONSUMER_SECRET)
        token = oauth.Token(auth.OAUTH_TOKEN, auth.OAUTH_TOKEN_SECRET)

        # Only thing different from regular smtplib
        self.conn.authenticate(auth.BASE_GMAIL_SMTP_UTL, consumer, token)


    def send_mail(self, msg_subject, msg_body):

        from_addr = 'mgrinich@gmail.com'
        to_addr = ['mgrinich@gmail.com']

        header = 'To: "John Doe (Test Header)" <test_to_header@gmail.com>\n' + \
                 'From: "Jane Doe" <test_from_header@gmail.com>\n' + \
                 'Subject:' + msg_subject + '\n'
                     
        msg = header + '\n' + msg_body + '\n\n'
        self.conn.sendmail(from_addr, to_addr, msg)

    def quit(self):
        self.conn.quit()


def main():
    log.basicConfig(level=log.DEBUG)
    s = SMTP()
    s.setup()
    s.send_mail("Test message", "Body content of test message!")
    s.quit()


if __name__ == "__main__":
    main()