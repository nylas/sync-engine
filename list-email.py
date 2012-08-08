import oauth2 as oauth
import oauth2.clients.imap as imaplib
import email


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
print conn.list()

