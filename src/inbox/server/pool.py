# monkey-patch so geventconnpool's @retry recognizes errors
import sys

from gevent import socket
from geventconnpool import ConnectionPool

import imaplib
imaplib.IMAP4.error = socket.error
imaplib.IMAP4.abort = socket.error

from imapclient import IMAPClient

from inbox.server.log import get_logger
log = get_logger()

from inbox.server.models import session_scope
from inbox.server.models.tables.imap import ImapAccount
from inbox.server.basicauth import AUTH_TYPES
from inbox.server import oauth
from inbox.server.auth.base import get_handler

IMAP_HOSTS = {'Gmail': 'imap.gmail.com',
                'Yahoo': 'imap.mail.yahoo.com'}

# Memory cache for per-user IMAP connection pool.
imapaccount_id_to_connection_pool = {}

DEFAULT_POOL_SIZE = 5


def verify_gmail_account(account):
    try:
        conn = IMAPClient(IMAP_HOSTS['Gmail'], use_uid=True, ssl=True)
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
                conn.oauth2_login(account.email_address, account.o_access_token)

    return conn


def verify_yahoo_account(account):
    try:
        conn = IMAPClient(IMAP_HOSTS['Yahoo'], use_uid=True, ssl=True)
    except IMAPClient.Error as e:
        raise socket.error(str(e))

    conn.debug = False
    try:
        conn.login(account.email_address, account.password)
    except IMAPClient.Error as e:
        print >>sys.stderr, '[ALERT] Invalid credentials (Failure)'
        sys.exit(1)

    return conn


def verify_imap_account(db_session, account):
    # issued_date = credentials.date
    # expires_seconds = credentials.o_expires_in

    # TODO check with expire date first
    # expire_date = issued_date + datetime.timedelta(seconds=expires_seconds)

    is_valid = oauth.validate_token(account.o_access_token)

    # TODO refresh tokens based on date instead of checking?
    # if not is_valid or expire_date > datetime.datetime.utcnow():
    if not is_valid:
        log.error('Need to update access token!')

        refresh_token = account.o_refresh_token

        log.error('Getting new access token...')
        response = oauth.get_new_token(refresh_token)  # TOFIX blocks
        response['refresh_token'] = refresh_token  # Propogate it through

        # TODO handling errors here for when oauth has been revoked
        if 'error' in response:
            log.error(response['error'])
            if response['error'] == 'invalid_grant':
                # Means we need to reset the entire oauth process.
                log.error('Refresh token is invalid.')
            return None

        # TODO Verify it and make sure it's valid.
        assert 'access_token' in response

        auth_handler = get_handler(account.email_address)
        account = auth_handler.create_account(db_session, account.email_address,
            response)
        log.info('Updated token for imap account {0}'.format(
            account.email_address))

    return account


def get_connection_pool(account_id, pool_size=None):
    if pool_size is None:
        pool_size = DEFAULT_POOL_SIZE

    pool = imapaccount_id_to_connection_pool.get(account_id)
    if pool is None:
        pool = imapaccount_id_to_connection_pool[account_id] \
                = IMAPConnectionPool(account_id, num_connections=pool_size)
    return pool


class IMAPConnectionPool(ConnectionPool):
    def __init__(self, account_id, num_connections=5):
        log.info('Creating connection pool for account {0} with {1} '\
                 'connections'.format(account_id, num_connections))
        self.account_id = account_id
        self._set_account_info()
        # 1200s == 20min
        ConnectionPool.__init__(self, num_connections, keepalive=1200)

    def _set_account_info(self):
        with session_scope() as db_session:
            account = db_session.query(ImapAccount).get(self.account_id)

            # Refresh token if need be, for OAuthed accounts
            if AUTH_TYPES.get(account.provider) == 'OAuth':
                account = verify_imap_account(db_session, account)
                self.o_access_token = account.o_access_token

            self.email_address = account.email_address
            self.provider = account.provider

    def _new_connection(self):
        with session_scope() as db_session:
            account = db_session.query(ImapAccount).get(self.account_id)

            if (account.provider == 'Gmail'):
                conn = verify_gmail_account(account)

            elif (account.provider == 'Yahoo'):
                conn = verify_yahoo_account(account)

            # Reads from db, therefore shouldn't get here
            else:
                raise

        return conn

    def _keepalive(self, c):
        c.noop()
