import socket

import sqlalchemy.orm.exc

from imapclient import IMAPClient

from inbox.auth.oauth import oauth_authorize
from inbox.auth.base import verify_imap_account
from inbox.models.session import session_scope
from inbox.models import Namespace
from inbox.models.backends.gmail import GmailAccount
from inbox.config import config


PROVIDER = 'gmail'
IMAP_HOST = 'imap.gmail.com'
PROVIDER_PREFIX = 'gmail'


def verify_gmail_account(account):
    try:
        conn = IMAPClient(IMAP_HOST, use_uid=True, ssl=True)
    except IMAPClient.Error as e:
        raise socket.error(str(e))

    conn.debug = False
    try:
        conn.oauth2_login(account.email_address, account.access_token)
    except IMAPClient.Error as e:
        if str(e) == '[ALERT] Invalid credentials (Failure)':
            # maybe refresh the access token
            with session_scope() as db_session:
                account = verify_imap_account(db_session, account)
                conn.oauth2_login(account.email_address,
                                  account.access_token)

    return conn


def create_auth_account(db_session, email_address):

    uri = config.get('GOOGLE_OAUTH_REDIRECT_URI', None)

    if uri != 'urn:ietf:wg:oauth:2.0:oob':
        raise NotImplementedError('Callback-based OAuth is not supported')

    response = auth_account(email_address)
    account = create_account(db_session, email_address, response)

    return account


def auth_account(email_address):
    return oauth_authorize(email_address)


def create_account(db_session, email_address, response):
    try:
        account = db_session.query(GmailAccount).filter_by(
            email_address=email_address).one()
    except sqlalchemy.orm.exc.NoResultFound:
        namespace = Namespace()
        account = GmailAccount(namespace=namespace)

    account.access_token = response.get('access_token')
    account.refresh_token = response.get('refresh_token')
    account.scope = response.get('scope')
    account.expires_in = response.get('expires_in')
    account.token_type = response.get('token_type')
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


def verify_account(db_session, account):
    verify_gmail_account(account)
    db_session.add(account)
    db_session.commit()

    return account
