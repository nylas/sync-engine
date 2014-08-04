import base64
import functools
from collections import namedtuple

import smtplib
import geventconnpool
from gevent import socket

from inbox.log import get_logger
from inbox.models.session import session_scope
from inbox.models.backends.imap import ImapAccount
from inbox.sendmail.base import SendMailException, SendError
from inbox.providers import provider_info
log = get_logger()

DEFAULT_POOL_SIZE = 2

# Memory cache for per-user SMTP connection pool.
account_id_to_connection_pool = {}

# TODO[k]: Other types (LOGIN, XOAUTH, PLAIN-CLIENTTOKEN, CRAM-MD5)
AUTH_EXTNS = {'oauth2': 'XOAUTH2',
              'password': 'PLAIN'}

AccountInfo = namedtuple('AccountInfo',
                         'id email provider auth_type auth_token')


def get_smtp_connection_pool(account_id, pool_size=None):
    pool_size = pool_size or DEFAULT_POOL_SIZE

    if account_id_to_connection_pool.get(account_id) is None:
        account_id_to_connection_pool[account_id] = \
            SMTPConnectionPool(account_id, num_connections=pool_size)

    return account_id_to_connection_pool[account_id]


smtpconn_retry = functools.partial(
    geventconnpool.retry, logger=log, interval=5, max_failures=5)


class SMTPConnection(object):
    def __init__(self, account, c, log):
        self.account_id = account.id
        self.email_address = account.email
        self.provider_name = account.provider
        self.auth_type = provider_info(self.provider_name)['auth']
        self.auth_token = account.auth_token

        self.connection = c

        self.log = log
        self.auth_handlers = {'oauth2': self.smtp_oauth2,
                              'password': self.smtp_password}

        self.setup()

    def __enter__(self):
        if not self.is_connected():
            self.reconnect()

        return self.connection

    def __exit__(self, type, value, traceback):
        try:
            self.connection.quit()
        except smtplib.SMTPServerDisconnected:
            return

    def setup(self):
        connection = self.connection

        # Put the SMTP connection in TLS mode
        connection.ehlo()

        if not connection.has_extn('starttls'):
            raise SendMailException('Required SMTP STARTTLS not supported.')

        connection.starttls()
        connection.ehlo()

        # Auth the connection
        self.auth_connection()

    def auth_connection(self):
        c = self.connection

        # Auth mechanisms supported by the server
        if not c.has_extn('auth'):
            raise SendMailException('Required SMTP AUTH not supported.')

        supported_types = c.esmtp_features['auth'].strip().split()

        # Auth mechanism needed for this account
        if AUTH_EXTNS.get(self.auth_type) not in supported_types:
            raise SendMailException(
                'Required SMTP Auth mechanism not supported.')

        auth_handler = self.auth_handlers.get(self.auth_type)
        auth_handler()

    # OAuth2 authentication
    def _smtp_oauth2_try_refresh(self):
        with session_scope() as db_session:
            account = db_session.query(ImapAccount).get(self.account_id)
            self.auth_token = account.renew_access_token()

    def smtp_oauth2(self):
        c = self.connection

        # Try to auth, but if it fails then try to refresh the access_token
        # and authenticate again.
        try:
            auth_string = 'user={0}\1auth=Bearer {1}\1\1'.\
                format(self.email_address, self.auth_token)
            c.docmd('AUTH', 'XOAUTH2 {0}'.format(
                base64.b64encode(auth_string)))
        except smtplib.SMTPAuthenticationError as e:
            self._smtp_oauth2_try_refresh()
            try:
                auth_string = 'user={0}\1auth=Bearer {1}\1\1'.\
                    format(self.email_address, self.auth_token)
                c.docmd('AUTH', 'XOAUTH2 {0}'.format(
                    base64.b64encode(auth_string)))
            except smtplib.SMTPAuthenticationError as e:
                self.log.error('SMTP Auth failed for: {0}'.format(
                    self.email_address))
                raise e

        self.log.info('SMTP Auth(OAuth2) success for: {0}'.format(
            self.email_address))

    # Password authentication
    def smtp_password(self):
        c = self.connection

        # Try to auth, but if it fails with the login function, try a manual
        # AUTH LOGIN (see: http://www.harelmalka.com/?p=94 )
        try:
            c.login(self.email_address, self.auth_token)
        except smtplib.SMTPAuthenticationError, e:
            try:
                c.docmd("AUTH LOGIN", base64.b64encode(self.email_address))
                c.docmd(base64.b64encode(self.auth_token), "")
            except smtplib.SMTPAuthenticationError as e:
                self.log.error('SMTP Auth failed for: {0}'.format(
                    self.email_address))
                raise e

        self.log.info('SMTP Auth(Password) success for: {0}'.format(
            self.email_address))

    def is_connected(self):
        try:
            status = self.connection.noop()[0]
        except smtplib.SMTPServerDisconnected:
            return False

        return (status == 250)

    def reconnect(self):
        try:
            host, port = provider_info(self.provider_name)['smtp'].split(':')
            self.connection.connect(str(host), int(port))
        except smtplib.SMTPConnectError:
            self.log.error('SMTPConnectError')
            raise

        self.setup()

    def keepalive(self):
        try:
            self.connection.noop()
        except smtplib.SMTPServerDisconnected:
            self.reconnect()

    def sendmail(self, email_address, recipients, msg):
        return self.connection.sendmail(email_address, recipients, msg)


class SMTPConnectionPool(geventconnpool.ConnectionPool):
    def __init__(self, account_id, num_connections, debug=False):
        self.log = get_logger()
        self.log.info('Creating SMTP connection pool for account {0} with {1} '
                      'connections'.format(account_id, num_connections))

        self.account_id = account_id
        self._set_account_info()

        self.debug = debug

        # 1200s == 20min
        geventconnpool.ConnectionPool.__init__(
            self, num_connections, keepalive=1200)

    def _set_account_info(self):
        with session_scope() as db_session:
            account = db_session.query(ImapAccount).get(self.account_id)

            self.email_address = account.email_address
            self.provider_name = account.provider
            self.sender_name = account.sender_name
            self.sent_folder = account.sent_folder.name

            self.auth_type = provider_info(self.provider_name)['auth']

            if self.auth_type == 'oauth2':
                self.auth_token = account.access_token
            else:
                assert self.auth_type == 'password'
                self.auth_token = account.password

    def _new_connection(self):
        try:
            host, port = provider_info(self.provider_name)['smtp'].split(':')
            connection = smtplib.SMTP(str(host), int(port))
        # Convert to a socket.error so geventconnpool will retry automatically
        # to establish new connections. We do this so the pool is resistant to
        # temporary connection errors.
        except smtplib.SMTPConnectError as e:
            self.log.error(str(e))
            raise socket.error('SMTPConnectError')

        connection.set_debuglevel(self.debug)

        account_info = AccountInfo(id=self.account_id,
                                   email=self.email_address,
                                   provider=self.provider_name,
                                   auth_type=self.auth_type,
                                   auth_token=self.auth_token)

        smtp_connection = SMTPConnection(account_info, connection, self.log)
        return smtp_connection

    def _keepalive(self, c):
        c.keepalive()


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
        self.sender_name = self.pool.sender_name
        self.email_address = self.pool.email_address
        self.sent_folder = self.pool.sent_folder

        self.log = get_logger()

    @smtpconn_retry
    def _send(self, recipients, msg):
        """ Send the email message over the network. """
        with self.pool.get() as smtpconn:
            with smtpconn:
                try:
                    failures = smtpconn.sendmail(self.email_address,
                                                 recipients, msg)
                # Sent to none successfully
                except smtplib.SMTPRecipientsRefused:
                    raise SendError(failures)

                except (smtplib.SMTPException, smtplib.SMTPServerDisconnected)\
                        as e:
                    self.log.error('Sending failed: Exception {0}'.format(e))
                    raise socket.error(
                        'Sending failed: Exception {0}'.format(e))
                # Send to at least one failed
                if failures:
                    raise SendError(failures)

                # Sent to all successfully
                self.log.info('Sending successful: {0} to {1}'.format(
                    self.email_address, ', '.join(recipients)))

    def _send_mail(self, recipients, mimemsg):
        """
        Send the email message, update the message stored in the local data
        store.

        The message is stored in the local data store as a draft message and
        is converted to a sent message so it is immediately available to the
        user as such (for e.g. if they search the `sent` folder).
        It is reconciled with the message we get from the remote backend
        on a subsequent sync of the folder (see inbox.models.util.py)

        """
        raise NotImplementedError

    def send_new(self, db_session, draft, recipients):
        """
        Send a previously created + saved draft email from this user account.

        Parameters
        ----------
        db_session
        draft : models.tables.base.Message object
            the draft message to send.
        recipients: Recipients(to, cc, bcc) namedtuple
            to, cc, bcc are a lists of utf-8 encoded strings or None.
        """
        raise NotImplementedError

    def send_reply(self, db_session, draft, recipients):
        """
        Send a previously created + saved draft email reply from this user
        account.

        Parameters
        ----------
        db_session
        draft : models.tables.base.Message object
            the draft message to send.
        recipients: Recipients(to, cc, bcc) namedtuple
            to, cc, bcc are a lists of utf-8 encoded strings or None.
        """
        raise NotImplementedError
