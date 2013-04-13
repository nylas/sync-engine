import oauth2 as oauth

try:
    from credentials import ACCOUNT, OAUTH_TOKEN, OAUTH_TOKEN_SECRET
except ImportError:
	print 'Go set your oAuth credentials in credentials.py!'

SSL = True

BASE_GMAIL_IMAP_URL = 'https://mail.google.com/mail/b/' + ACCOUNT + '/imap/'
BASE_GMAIL_SMTP_UTL = 'https://mail.google.com/mail/b/' + ACCOUNT + '/smtp/'

IMAP_HOST = 'imap.gmail.com'
SMTP_HOST = 'smtp.gmail.com'

# Eventually need to register this app with Google
# https://accounts.google.com/ManageDomains
CONSUMER_KEY = 'anonymous'
CONSUMER_SECRET = 'anonymous'

