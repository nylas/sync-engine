import base64
import smtplib
from geventconnpool import ConnectionPool

from inbox.server.log import get_logger
from inbox.server.basicauth import AUTH_TYPES
from inbox.server.auth.base import verify_imap_account
from inbox.server.models import session_scope
from inbox.server.models.tables.imap import ImapAccount

SMTP_HOSTS = {'Gmail': 'smtp.gmail.com'}
SMTP_PORT = 587

DEFAULT_POOL_SIZE = 5

# Memory cache for per-user SMTP connection pool.
account_id_to_connection_pool = {}

# TODO[k]: Other types (LOGIN, XOAUTH, PLAIN-CLIENTTOKEN, CRAM-MD5)
AUTH_EXTNS = {'OAuth': 'XOAUTH2',
              'Password': 'PLAIN'}


class SendMailError(Exception):
    pass


def get_smtp_connection_pool(account_id, pool_size=None):
    pool_size = pool_size or DEFAULT_POOL_SIZE

    if account_id_to_connection_pool.get(account_id) is None:
        account_id_to_connection_pool[account_id] = \
            SMTPConnectionPool(account_id, num_connections=pool_size)

    return account_id_to_connection_pool[account_id]


class SMTPConnection():
    def __init__(self, c):
        self.connection = c

    def __enter__(self):
        return self.connection

    def __exit__(self, type, value, traceback):
        self.connection.quit()


class SMTPConnectionPool(ConnectionPool):
    def __init__(self, account_id, num_connections=5, debug=False):
        self.log = get_logger(account_id, 'sendmail: connection_pool')
        self.log.info('Creating SMTP connection pool for account {0} with {1} '
                      'connections'.format(account_id, num_connections))

        self.account_id = account_id
        self._set_account_info()

        self.debug = debug

        self.auth_handlers = {'OAuth': self.smtp_oauth,
                              'Password': self.smtp_password}

        # 1200s == 20min
        ConnectionPool.__init__(self, num_connections, keepalive=1200)

    def _set_account_info(self):
        with session_scope() as db_session:
            account = db_session.query(ImapAccount).get(self.account_id)

            self.email_address = account.email_address
            self.provider = account.provider
            self.full_name = account.full_name if account.provider == 'Gmail'\
                else ''
            self.auth_type = AUTH_TYPES.get(account.provider)

            if self.auth_type == 'OAuth':
                # Refresh OAuth token if need be
                account = verify_imap_account(db_session, account)
                self.o_access_token = account.o_access_token
            else:
                assert self.auth_type == 'Password'
                self.password = account.password

    def _new_connection(self):
        try:
            connection = smtplib.SMTP(SMTP_HOSTS[self.provider], SMTP_PORT)
        except smtplib.SMTPConnectError as e:
            self.log.error('SMTPConnectError')
            raise e

        connection.set_debuglevel(self.debug)

        # Put the SMTP connection in TLS mode
        connection.ehlo()

        if not connection.has_extn('starttls'):
            raise SendMailError('Required SMTP STARTTLS not supported.')

        connection.starttls()
        connection.ehlo()

        # Auth the connection
        authed_connection = self.auth_connection(connection)

        return authed_connection

    def _keepalive(self, c):
        c.noop()

    def auth_connection(self, c):
        # Auth mechanisms supported by the server
        if not c.has_extn('auth'):
            raise SendMailError('Required SMTP AUTH not supported.')

        supported_types = c.esmtp_features['auth'].strip().split()

        # Auth mechanism needed for this account
        if AUTH_EXTNS.get(self.auth_type) not in supported_types:
            raise SendMailError('Required SMTP Auth mechanism not supported.')

        auth_handler = self.auth_handlers.get(self.auth_type)
        return auth_handler(c)

    # OAuth2 authentication
    def smtp_oauth(self, c):
        try:
            auth_string = 'user={0}\1auth=Bearer {1}\1\1'.\
                format(self.email_address, self.o_access_token)
            c.docmd('AUTH', 'XOAUTH2 {0}'.format(
                base64.b64encode(auth_string)))
        except smtplib.SMTPAuthenticationError as e:
            self.log.error('SMTP Auth failed for: {0}'.format(
                self.email_address))
            raise e

        self.log.info('SMTP Auth success for: {0}'.format(self.email_address))
        return c

    # Password authentication
    def smtp_password(self, c):
        raise NotImplementedError


class SMTPClient(object):
    """
    Base class for an SMTPClient.
    The SMTPClient is responsible for creating/closing SMTP connections
    and sending mail.

    Subclasses must implement the _send_mail, send_new & send_reply functions.

    """
    def __init__(self, account_id, account_namespace):
        self.account_id = account_id
        self.namespace = account_namespace
        self.pool = get_smtp_connection_pool(self.account_id)
        # Required for Gmail
        self.full_name = self.pool.full_name
        self.email_address = self.pool.email_address

        self.log = get_logger(account_id, 'sendmail')

    def _send(self, recipients, msg):
        """ Send the email message over the network. """
        with self.pool.get() as c:
            with SMTPConnection(c) as smtpconn:
                try:
                    failures = smtpconn.sendmail(self.email_address,
                                                 recipients, msg)
                # Sent to none successfully
                # TODO[k]: Retry
                except smtplib.SMTPException as e:
                    self.log.error('Sending failed: Exception {0}'.format(e))
                    raise

                # Sent to all successfully
                if not failures:
                    self.log.info('Sending successful: {0} to {1}'.format(
                        self.email_address, ', '.join(recipients)))
                    return True

                # Sent to atleast one successfully
                # TODO[k]: Handle this!
                for r, e in failures.iteritems():
                    self.log.error('Send failed: {0} to {1}, code: {2}'.format(
                        self.email_address, r, e[0]))
                    return False

    def _send_mail(self, recipients, mimemsg):
        """
        Send the email message, store it to the local data store.

        The message is stored in the local data store so it is immediately
        available to the user (for e.g. if they search the `sent` folder).
        It is reconciled with the message we get from the remote backend
        on a subsequent sync of that folder (see server/models/message.py)

        """
        raise NotImplementedError

    def send_new(self, recipients, subject, body, attachments=None):
        """
        Send an email from this user account.

        Parameters
        ----------
        recipients: Recipients(to, cc, bcc) namedtuple
            to, cc, bcc are a lists of utf-8 encoded strings or None.
        subject : string
            a utf-8 encoded string
        body : string
            a utf-8 encoded string
        attachments: list of dicts, optional
            a list of dicts(filename, data, content_type)

        """
        raise NotImplementedError

    def send_reply(self, thread_id, recipients, subject, body,
                   attachments=None):
        """
        Send an email reply from this user account.

        Parameters
        ----------
        thread_id: int
        recipients: Recipients(to, cc, bcc) namedtuple
            to, cc, bcc are a lists of utf-8 encoded strings or None.
        subject : string
            a utf-8 encoded string
        body : string
            a utf-8 encoded string
        attachments: list of dicts, optional
            a list of dicts(filename, data, content_type)

        """
        raise NotImplementedError
