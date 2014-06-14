import datetime
import socket
import time

import sqlalchemy.orm.exc
import requests

from imapclient import IMAPClient

from inbox.auth.oauth import oauth_authorize
from inbox.auth.base import verify_imap_account
from inbox.models.session import session_scope
from inbox.models import Namespace
from inbox.models.backends.imap import ImapAccount
from inbox.config import config


PROVIDER = 'Gmail'
IMAP_HOST = 'imap.gmail.com'
PROVIDER_PREFIX = 'gmail'


def verify_gmail_account(account):
    try:
        conn = IMAPClient(IMAP_HOST, use_uid=True, ssl=True)
    except IMAPClient.Error as e:
        raise socket.error(str(e))

    conn.debug = False
    try:
        conn.oauth2_login(account.email_address, account.o_access_token)
    except IMAPClient.Error as e:
        if str(e) == '[ALERT] Invalid credentials (Failure)':
            # maybe refresh the access token
            with session_scope() as db_session:
                account = verify_imap_account(db_session, account)
                conn.oauth2_login(account.email_address,
                                  account.o_access_token)

    return conn


def create_auth_account(db_session, email_address):

    uri = config.get('GOOGLE_OAUTH_REDIRECT_URI', None)

    if uri != 'urn:ietf:wg:oauth:2.0:oob':
        raise NotImplementedError("callback-based OAuth is not supported")

    response = auth_account(email_address)
    account = create_account(db_session, email_address, response)

    return account


def auth_account(email_address):
    return oauth_authorize(email_address)


def create_account(db_session, email_address, response):
    try:
        account = db_session.query(ImapAccount).filter_by(
            email_address=email_address).one()
    except sqlalchemy.orm.exc.NoResultFound:
        namespace = Namespace()
        account = ImapAccount(namespace=namespace)

    account.provider = 'Gmail'
    account.provider_prefix = PROVIDER_PREFIX
    account.imap_host = IMAP_HOST
    account.email_address = response['email']
    account.o_token_issued_to = response['issued_to']
    account.o_user_id = response['user_id']
    account.o_access_token = response['access_token']
    account.o_id_token = response['id_token']
    account.o_expires_in = response['expires_in']
    account.o_access_type = response['access_type']
    account.o_token_type = response['token_type']
    account.o_audience = response['audience']
    account.o_scope = response['scope']
    account.o_email = response['email']
    account.o_refresh_token = response['refresh_token']
    account.o_verified_email = response['verified_email']
    account.date = datetime.datetime.utcnow()

    if 'given_name' in response:
        account.given_name = response['given_name']
    if 'family_name' in response:
        account.family_name = response['family_name']
    if 'locale' in response:
        account.g_locale = response['locale']
    if 'locale' in response:
        account.picture = response['picture']
    if 'gender' in response:
        account.g_gender = response['gender']
    if 'link' in response:
        account.g_plus_url = response['link']
    if 'id' in response:
        account.google_id = response['id']

    return account


def verify_account(db_session, account):
    verify_gmail_account(account)
    db_session.add(account)
    db_session.commit()

    return account
