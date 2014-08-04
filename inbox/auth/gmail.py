import sys
from sqlalchemy.orm.exc import NoResultFound

from inbox.oauth import oauth_authorize_console
from inbox.models import Namespace
from inbox.models.backends.gmail import GmailAccount, IMAP_HOST
from inbox.config import config
from inbox.auth.oauth import connect_account as oauth_connect_account
from inbox.auth.oauth import verify_account as oauth_verify_account

from inbox.log import get_logger
log = get_logger()

PROVIDER = 'gmail'

# Google OAuth app credentials
OAUTH_CLIENT_ID = config.get_required('GOOGLE_OAUTH_CLIENT_ID')
OAUTH_CLIENT_SECRET = config.get_required('GOOGLE_OAUTH_CLIENT_SECRET')
OAUTH_REDIRECT_URI = config.get_required('GOOGLE_OAUTH_REDIRECT_URI')

OAUTH_AUTHENTICATE_URL = 'https://accounts.google.com/o/oauth2/auth'
OAUTH_ACCESS_TOKEN_URL = 'https://accounts.google.com/o/oauth2/token'
OAUTH_TOKEN_VALIDATION_URL = 'https://www.googleapis.com/oauth2/v1/tokeninfo'
OAUTH_USER_INFO_URL = 'https://www.googleapis.com/oauth2/v1/userinfo'

OAUTH_SCOPE = ' '.join([
    'https://www.googleapis.com/auth/userinfo.email',  # email address
    'https://www.googleapis.com/auth/userinfo.profile',  # G+ profile
    'https://mail.google.com/',  # email
    'https://www.google.com/m8/feeds',  # contacts
    'https://www.googleapis.com/auth/calendar'  # calendar
])


def _this_module():
    return sys.modules[__name__]


def create_auth_account(db_session, email_address, token, exit):
    uri = config.get('GOOGLE_OAUTH_REDIRECT_URI', None)

    if uri != 'urn:ietf:wg:oauth:2.0:oob':
        raise NotImplementedError('Callback-based OAuth is not supported')

    response = auth_account(email_address, token, exit)
    account = create_account(db_session, email_address, response)

    return account


def auth_account(email_address, token, exit):
    if not token:
        print ("To authorize Inbox, visit this url and follow the directions:")
    return oauth_authorize_console(_this_module(), email_address, token, exit)


def create_account(db_session, email_address, response):
    # See if the account exists in db, otherwise create it
    try:
        account = db_session.query(GmailAccount) \
            .filter_by(email_address=email_address).one()
    except NoResultFound:
        namespace = Namespace()
        account = GmailAccount(namespace=namespace)

    tok = response.get('access_token')
    expires_in = response.get('expires_in')
    account.set_access_token(tok, expires_in)
    account.refresh_token = response.get('refresh_token')
    account.scope = response.get('scope')
    account.email_address = response.get('email')
    account.family_name = response.get('family_name')
    account.given_name = response.get('given_name')
    account.name = response.get('name')
    account.gender = response.get('gender')
    account.g_id = response.get('id')
    account.g_user_id = response.get('user_id')
    account.g_id_token = response.get('id_token')
    account.link = response.get('link')
    account.locale = response.get('locale')
    account.picture = response.get('picture')
    account.home_domain = response.get('hd')
    account.client_id = response.get('client_id')
    account.client_secret = response.get('client_secret')

    return account


def connect_account(account):
    return oauth_connect_account(account, IMAP_HOST)


def verify_account(account):
    return oauth_verify_account(account, IMAP_HOST)
