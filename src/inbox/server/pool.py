# monkey-patch so geventconnpool's @retry recognizes errors
from gevent import socket
import imaplib
imaplib.IMAP4.error = socket.error
imaplib.IMAP4.abort = socket.error

from geventconnpool import ConnectionPool

from imapclient import IMAPClient

from .models import session_scope
from .models.tables import ImapAccount
from .session import verify_imap_account
from .log import get_logger
log = get_logger()

IMAP_HOSTS = { 'Gmail': 'imap.gmail.com',
                'Yahoo': 'imap.mail.yahoo.com' }

# Memory cache for per-user IMAP connection pool.
imapaccount_id_to_connection_pool = {}

DEFAULT_POOL_SIZE = 5

def verify_gmail_account(access_token_dict):
    try:
        conn = IMAPClient(IMAP_HOSTS[provider], use_uid=True, ssl=True)
    except IMAPClient.Error as e:
        raise socket.error(str(e))

    conn.debug = False

    try:
        conn.oauth2_login(access_token_dict['email'], access_token_dict['access_token'])
    except IMAPClient.Error as e:
        if str(e) == '[ALERT] Invalid credentials (Failure)':
            print >>sys.stderr, str(e)
            sys.exit(1)

    user = User()
    namespace = Namespace()
    account = ImapAccount(user=user, namespace=namespace)
    account.email_address = access_token_dict['email']
    account.o_token_issued_to = access_token_dict['issued_to']
    account.o_user_id = access_token_dict['user_id']
    account.o_access_token = access_token_dict['access_token']
    account.o_id_token = access_token_dict['id_token']
    account.o_expires_in = access_token_dict['expires_in']
    account.o_access_type = access_token_dict['access_type']
    account.o_token_type = access_token_dict['token_type']
    account.o_audience = access_token_dict['audience']
    account.o_scope = access_token_dict['scope']
    account.o_email = access_token_dict['email']
    account.o_refresh_token = access_token_dict['refresh_token']
    account.o_verified_email = access_token_dict['verified_email']
    account.date = datetime.datetime.utcnow()
    account.provider = 'Gmail'

    return account

def verify_yahoo_account(email_pw_dict):
    try:
        conn.login(email_pw_dict['email'], email_pw_dict['password'])
    except IMAPClient.Error as e:
        print >>sys.stderr, '[ALERT] Invalid credentials (Failure)'
        sys.exit(1)

    user = User()
    namespace = Namespace()
    account = ImapAccount(user=user, namespace=namespace)
    account.email_address = email_pw_dict['email']
    account.password = email_pw_dict['password']
    account.is_oauthed = False
    account.date = datetime.datetime.utcnow()
    account.provider = 'Yahoo'

    return account

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
            account = verify_imap_account(db_session,
                    db_session.query(ImapAccount).get(self.account_id))
            self.imap_host = IMAP_HOSTS[account.provider]
            self.o_access_token = account.o_access_token
            self.email_address = account.email_address

    def _new_connection(self):
        try:
            conn = IMAPClient(self.imap_host, use_uid=True, ssl=True)
        except IMAPClient.Error as e:
            raise socket.error(str(e))

        conn.debug = False

        try:
            conn.oauth2_login(self.email_address, self.o_access_token)
        except IMAPClient.Error as e:
            if str(e) == '[ALERT] Invalid credentials (Failure)':
                self._set_account_info()
                conn.oauth2_login(self.email_address, self.o_access_token)

        return conn

    def _keepalive(self, c):
        c.noop()
