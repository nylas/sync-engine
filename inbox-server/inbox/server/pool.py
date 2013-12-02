# monkey-patch so geventconnpool's @retry recognizes errors
from gevent import socket
import imaplib
imaplib.IMAP4.error = socket.error

from geventconnpool import ConnectionPool

from imapclient import IMAPClient

from .session import verify_imap_account

IMAP_HOSTS = { 'Gmail': 'imap.gmail.com' }

# Memory cache for per-user IMAP connection pool.
imapaccount_id_to_connection_pool = {}

def get_connection_pool(account):
    pool = imapaccount_id_to_connection_pool.get(account.id)
    if pool is None:
        pool = imapaccount_id_to_connection_pool[account.id] \
                = IMAPConnectionPool(account)
    return pool

class IMAPConnectionPool(ConnectionPool):
    def __init__(self, account, num_connections=5):
        self.account = verify_imap_account(account)
        # 1200s == 20min
        ConnectionPool.__init__(self, num_connections, keepalive=1200)

    def _new_connection(self):
        imap_host = IMAP_HOSTS[self.account.provider]

        try:
            conn = IMAPClient(imap_host, use_uid=True, ssl=True)
        except IMAPClient.Error as e:
            raise socket.error(str(e))

        conn.debug = False

        try:
            conn.oauth2_login(self.account.email_address, self.account.o_access_token)
        except IMAPClient.Error as e:
            if str(e) == '[ALERT] Invalid credentials (Failure)':
                self.account = verify_imap_account(self.account)
                conn.oauth2_login(
                        self.account.email_address, self.account.o_access_token)

        return conn

    def _keepalive(self, c):
        c.noop()
