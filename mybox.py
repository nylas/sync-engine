import tornado.ioloop
import tornado.web
import tornado.template

import oauth2 as oauth
import oauth2.clients.imap as imaplib
import email

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

status, data = conn.uid('fetch', uid, 'RFC822')



print my_mailboxes