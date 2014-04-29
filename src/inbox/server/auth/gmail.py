import datetime
import socket
import time

import sqlalchemy.orm.exc
import requests

from imapclient import IMAPClient

from inbox.server.oauth import oauth
from inbox.server.auth.base import verify_imap_account
from inbox.server.models import session_scope
from inbox.server.models.tables.base import User, Namespace
from inbox.server.models.tables.imap import ImapAccount
from inbox.server.config import config

from inbox.server.auth.base import commit_account

PROVIDER = 'Gmail'
IMAP_HOST = 'imap.gmail.com'


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
    assert uri, 'Must define GOOGLE_OAUTH_REDIRECT_URI'

    def is_alive():
        try:
            # Note that we're using a self-signed SSL cert, so we disable
            # verification of the cert chain
            resp = requests.get(uri + '/alive', verify=False)
            if resp.status_code is 200:
                return True
            else:
                raise Exception('OAuth callback server detected, \
                    but returned {0}'.format(resp.status_code))
        except requests.exceptions.ConnectionError:
            return False

    if uri != 'urn:ietf:wg:oauth:2.0:oob' and not is_alive():
        print """\033[93m \n\n
Hey you! It looks like you're not using the Google oauth 'installed'
app type, meaning you need a web oauth callback. The easiest way
to do this is to run the stub flask app. :\n
        sudo tools/oauth_callback_server/start \n
Make sure that {0} is directed to your VM by editing /etc/hosts
on the host machine\n
Go ahead and start it. I'll wait for a minute...\n
\033[0m""".format(uri)

        while True:
            if is_alive():
                print 'Good to go!'
                break
            else:
                time.sleep(.5)

    response = auth_account(email_address)
    account = create_account(db_session, email_address, response)

    return account


def auth_account(email_address):
    return oauth(email_address)


def create_account(db_session, email_address, response):
    try:
        account = db_session.query(ImapAccount).filter_by(
            email_address=email_address).one()
    except sqlalchemy.orm.exc.NoResultFound:
        user = User()
        namespace = Namespace()
        account = ImapAccount(user=user, namespace=namespace)

    account.provider = 'Gmail'
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
    commit_account(db_session, account)

    return account
