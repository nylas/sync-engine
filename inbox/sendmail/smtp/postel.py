import base64
from collections import namedtuple

import smtplib

from inbox.log import get_logger
from inbox.models import Folder
from inbox.models.session import session_scope
from inbox.models.backends.imap import ImapAccount
from inbox.sendmail.base import SendMailException, SendError
from inbox.basicauth import OAuthError
from inbox.providers import provider_info
log = get_logger()

# TODO[k]: Other types (LOGIN, XOAUTH, PLAIN-CLIENTTOKEN, CRAM-MD5)
AUTH_EXTNS = {'oauth2': 'XOAUTH2',
              'password': 'PLAIN'}

SMTP_OVER_SSL_PORT = 465

AccountInfo = namedtuple('AccountInfo',
                         'id email provider auth_type auth_token')


class SMTPConnection(object):
    def __init__(self, account_id, email_address, provider_name, auth_type,
                 auth_token, smtp_endpoint, log):
        self.account_id = account_id
        self.email_address = email_address
        self.provider_name = provider_name
        self.auth_type = auth_type
        self.auth_token = auth_token
        self.smtp_endpoint = smtp_endpoint
        self.log = log
        self.log.bind(account_id=self.account_id)
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
        host, port = self.smtp_endpoint
        if port == SMTP_OVER_SSL_PORT:
            self.connection = smtplib.SMTP_SSL()
            self.connection.connect(host, port)
        else:
            self.connection = smtplib.SMTP()
            self.connection.connect(host, port)
            # Put the SMTP connection in TLS mode
            self.connection.ehlo()
            if not self.connection.has_extn('starttls'):
                raise SendMailException('Required SMTP STARTTLS not '
                                        'supported.')
            self.connection.starttls()

        # Auth the connection
        self.connection.ehlo()
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
                self.log.error('SMTP Auth failed')
                raise e

        self.log.info('SMTP Auth(Password) success')

    def is_connected(self):
        try:
            status = self.connection.noop()[0]
        except smtplib.SMTPServerDisconnected:
            return False

        return (status == 250)

    def reconnect(self):
        try:
            host, port = provider_info(self.provider_name,
                                       self.email_address)['smtp']
            self.connection.connect(host, port)
        except smtplib.SMTPConnectError:
            self.log.error('SMTPConnectError')
            raise

        self.setup()

    def sendmail(self, email_address, recipients, msg):
        return self.connection.sendmail(email_address, recipients, msg)


class BaseSMTPClient(object):
    """
    Base class for an SMTPClient.
    The SMTPClient is responsible for creating/closing SMTP connections
    and sending mail.

    Subclasses must implement the _send_mail, send_new & send_reply functions.

    """
    def __init__(self, account_id):
        self.account_id = account_id
        self.log = get_logger()
        self.log.bind(account_id=account_id)

        with session_scope() as db_session:
            account = db_session.query(ImapAccount).get(self.account_id)

            self.email_address = account.email_address
            self.provider_name = account.provider
            self.sender_name = account.name
            self.smtp_endpoint = account.smtp_endpoint

            if account.sent_folder is None:
                # account has no detected sent folder - create one.
                sent_folder = Folder.find_or_create(db_session, account,
                                                    'sent', 'sent')
                account.sent_folder = sent_folder

            self.sent_folder = account.sent_folder.name

            self.auth_type = provider_info(self.provider_name,
                                           self.email_address)['auth']

            if self.auth_type == 'oauth2':
                try:
                    self.auth_token = account.access_token
                except OAuthError:
                    raise SendMailException('Error logging in.')
            else:
                assert self.auth_type == 'password'
                self.auth_token = account.password

    def _send(self, recipients, msg):
        """ Send the email message over the network. """
        try:
            with self._get_connection() as smtpconn:
                failures = smtpconn.sendmail(self.email_address, recipients,
                                             msg)
            # Sent to none successfully
        except smtplib.SMTPRecipientsRefused:
            raise SendError('Refused', failures=failures)
        except smtplib.SMTPException as e:
            raise SendError('Sending failed: Exception {0}'.format(e))
        # Send to at least one failed
        if failures:
            raise SendError('Send failed', failures=failures)

        # Sent to all successfully
        self.log.info('Sending successful', sender=self.email_address,
                      recipients=recipients)

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

    def _get_connection(self):
        smtp_connection = SMTPConnection(account_id=self.account_id,
                                         email_address=self.email_address,
                                         provider_name=self.provider_name,
                                         auth_type=self.auth_type,
                                         auth_token=self.auth_token,
                                         smtp_endpoint=self.smtp_endpoint,
                                         log=self.log)
        return smtp_connection
