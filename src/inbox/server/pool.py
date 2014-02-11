# monkey-patch so geventconnpool's @retry recognizes errors
import datetime
import sys

from gevent import socket
import imaplib
imaplib.IMAP4.error = socket.error
imaplib.IMAP4.abort = socket.error

from geventconnpool import ConnectionPool

from imapclient import IMAPClient

from .models import session_scope
from .models.tables import ImapAccount, User, Namespace
from .session import verify_imap_account
from .oauth import AUTH_TYPES
from .log import get_logger
log = get_logger()

IMAP_HOSTS = { 'Gmail': 'imap.gmail.com',
                'Yahoo': 'imap.mail.yahoo.com' }

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

def get_connection_pool(account_id):
    pool = imapaccount_id_to_connection_pool.get(account_id)
    if pool is None:
        pool = imapaccount_id_to_connection_pool[account_id] \
                = IMAPConnectionPool(account_id, num_connections=pool_size)
    return pool

class IMAPConnectionPool(ConnectionPool):
    def __init__(self, account_id, num_connections=5):
        log.info("Creating connection pool for account {0} with {1} connections" \
                .format(account_id, num_connections))
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
            #self.account = account
            
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
