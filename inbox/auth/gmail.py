import socket

from sqlalchemy.orm.exc import NoResultFound

from imapclient import IMAPClient

from inbox.auth.oauth import oauth_authorize_console
from inbox.models import Namespace
from inbox.models.backends.gmail import GmailAccount
from inbox.config import config

from inbox.log import get_logger
log = get_logger()

PROVIDER = 'gmail'
IMAP_HOST = 'imap.gmail.com'
PROVIDER_PREFIX = 'gmail'


def create_auth_account(db_session, email_address):
    uri = config.get('GOOGLE_OAUTH_REDIRECT_URI', None)

    if uri != 'urn:ietf:wg:oauth:2.0:oob':
        raise NotImplementedError('Callback-based OAuth is not supported')

    response = auth_account(email_address)
    account = create_account(db_session, email_address, response)

    return account


def auth_account(email_address):
    return oauth_authorize_console(email_address)


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

    return account


# Used by the 'inbox-auth' program after we create an authenticated account
# as well as by a migration which imports gmail accounts from an old db
def verify_account(account):
    try:
        conn = IMAPClient(IMAP_HOST, use_uid=True, ssl=True)
    except IMAPClient.Error as e:
        raise socket.error(str(e))

    conn.debug = False
    try:
        conn.oauth2_login(account.email_address, account.access_token)
    except IMAPClient.Error as e:
        log.info("IMAP Login error, refresh auth token for: {}"
                 .format(account.email_address))
        if str(e) == '[ALERT] Invalid credentials (Failure)':
            # maybe the access token expired?
            conn.oauth2_login(account.email_address,
                              account.renew_access_token())

    return conn
