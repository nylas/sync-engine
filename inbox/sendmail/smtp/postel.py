import base64
import itertools

import smtplib

from inbox.log import get_logger
from inbox.models.session import session_scope
from inbox.models.backends.imap import ImapAccount
from inbox.models.backends.oauth import token_manager
from inbox.sendmail.base import generate_attachments, SendMailException
from inbox.sendmail.message import create_email
from inbox.basicauth import OAuthError
from inbox.providers import provider_info
log = get_logger()

# TODO[k]: Other types (LOGIN, XOAUTH, PLAIN-CLIENTTOKEN, CRAM-MD5)
AUTH_EXTNS = {'oauth2': 'XOAUTH2',
              'password': 'PLAIN'}

SMTP_OVER_SSL_PORT = 465


class SMTPConnection(object):
    def __init__(self, account_id, email_address, auth_type,
                 auth_token, smtp_endpoint, log):
        self.account_id = account_id
        self.email_address = email_address
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
        return self

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
            self.auth_token = token_manager.get_token(account,
                                                      force_refresh=True)

    def _try_xoauth2(self):
        auth_string = 'user={0}\1auth=Bearer {1}\1\1'.\
            format(self.email_address, self.auth_token)
        code, resp = self.connection.docmd('AUTH', 'XOAUTH2 {0}'.format(
            base64.b64encode(auth_string)))
        if code == 235:
            self.log.info('SMTP Auth(OAuth2) success',
                          email_address=self.email_address)
            return True
        else:
            log.error('Error in SMTP XOAUTH2 authentication',
                      response_code=code, response_line=resp)
            return False

    def smtp_oauth2(self):
        # Try to auth, but if it fails then try to refresh the access_token
        # and authenticate again.
        auth_success = self._try_xoauth2()
        if not auth_success:
            self._smtp_oauth2_try_refresh()
            auth_success = self._try_xoauth2()
        if not auth_success:
            raise SendMailException(
                'Could not authenticate with the SMTP server.', 403)

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
            host, port = self.smtp_endpoint
            self.connection.connect(host, port)
        except smtplib.SMTPConnectError:
            self.log.error('SMTPConnectError')
            raise

        self.setup()

    def sendmail(self, recipients, msg):
        return self.connection.sendmail(self.email_address, recipients, msg)


class SMTPClient(object):
    """ SMTPClient for Gmail and other IMAP providers. """
    def __init__(self, account):
        self.account_id = account.id
        self.log = get_logger()
        self.log.bind(account_id=account.id)
        self.email_address = account.email_address
        self.provider_name = account.provider
        self.sender_name = account.name
        self.smtp_endpoint = account.smtp_endpoint
        self.auth_type = provider_info(self.provider_name,
                                       self.email_address)['auth']

        if self.auth_type == 'oauth2':
            try:
                self.auth_token = token_manager.get_token(account)
            except OAuthError:
                raise SendMailException(
                    'Could not authenticate with the SMTP server.', 403)
        else:
            assert self.auth_type == 'password'
            self.auth_token = account.password

    def _send(self, recipients, msg):
        """ Send the email message over the network. """
        try:
            with self._get_connection() as smtpconn:
                failures = smtpconn.sendmail(recipients, msg)
        except smtplib.SMTPException as err:
            self._handle_sending_exception(err)
        if failures:
            # At least one recipient was rejected by the server.
            raise SendMailException('Sending to at least one recipent '
                                    'failed', 402, failures=failures)

        # Sent to all successfully
        self.log.info('Sending successful', sender=self.email_address,
                      recipients=recipients)

    def _handle_sending_exception(self, err):
        self.log.error("Error sending", error=err, exc_info=True)
        if isinstance(err, smtplib.SMTPServerDisconnected):
            raise SendMailException('The server unexpectedly closed the '
                                    'connection', 503)
        elif (isinstance(err, smtplib.SMTPDataError) and err.smtp_code == 550
              and err.smtp_error.startswith('5.4.5')):
            # Gmail-specific quota exceeded error.
            raise SendMailException('Daily sending quota exceeded', 429)
        elif isinstance(err, smtplib.SMTPRecipientsRefused):
            raise SendMailException('Sending to all recipients failed', 402)
        else:
            raise SendMailException('Sending failed: {}'.format(err), 503)

    def send(self, draft):
        """
        Turn a draft object into a MIME message and send it.

        Parameters
        ----------
        draft : models.message.Message object
            the draft message to send.
        """
        blocks = [p.block for p in draft.attachments]
        attachments = generate_attachments(blocks)

        # Note that we intentionally don't set the Bcc header in the message we
        # construct.
        msg = create_email(sender_name=self.sender_name,
                           sender_email=self.email_address,
                           inbox_uid=draft.inbox_uid,
                           to_addr=draft.to_addr,
                           cc_addr=draft.cc_addr,
                           bcc_addr=None,
                           subject=draft.subject,
                           html=draft.sanitized_body,
                           in_reply_to=draft.in_reply_to,
                           references=draft.references,
                           attachments=attachments)

        recipient_emails = [email for name, email in itertools.chain(
            draft.to_addr, draft.cc_addr, draft.bcc_addr)]
        return self._send(recipient_emails, msg)

    def _get_connection(self):
        smtp_connection = SMTPConnection(account_id=self.account_id,
                                         email_address=self.email_address,
                                         auth_type=self.auth_type,
                                         auth_token=self.auth_token,
                                         smtp_endpoint=self.smtp_endpoint,
                                         log=self.log)
        return smtp_connection
