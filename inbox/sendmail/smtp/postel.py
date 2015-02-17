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

SMTP_MAX_RETRIES = 1
SMTP_OVER_SSL_PORT = 465

# Relevant protocol constants; see
# https://tools.ietf.org/html/rfc4954 and
# https://support.google.com/a/answer/3726730?hl=en
SMTP_AUTH_SUCCESS = 235
SMTP_AUTH_CHALLENGE = 334
SMTP_TEMP_AUTH_FAIL = 454


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
        if code == SMTP_AUTH_CHALLENGE:
            log.error('Challenge in SMTP XOAUTH2 authentication',
                      response_code=code, response_line=resp)
            # Handle server challenge so that we can properly retry with the
            # connection.
            code, resp = self.connection.noop()
        if code != SMTP_AUTH_SUCCESS:
            log.error('SMTP XOAUTH2 error response',
                      response_code=code, response_line=resp)
        return code, resp

    def smtp_oauth2(self):
        code, resp = self._try_xoauth2()
        # If auth failed, try to refresh the access token and try again.
        if code != SMTP_AUTH_SUCCESS:
            self._smtp_oauth2_try_refresh()
            code, resp = self._try_xoauth2()
            # Propagate known temporary authentication issues as such.
            if code == SMTP_TEMP_AUTH_FAIL and resp.startswith('4.7.0'):
                raise SendMailException('Temporary error authenticating with '
                                        'the SMTP server', 503)
        if code != SMTP_AUTH_SUCCESS:
            raise SendMailException(
                'Could not authenticate with the SMTP server.', 403)
        self.log.info('SMTP Auth(OAuth2) success',
                      email_address=self.email_address)

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
        """Send the email message. Retries up to SMTP_MAX_RETRIES times if the
        message couldn't be submitted to any recipient.

        Parameters
        ----------
        recipients: list
            list of recipient email addresses.
        msg: string
            byte-encoded MIME message.

        Raises
        ------
        SendMailException
            If the message couldn't be sent to all recipients successfully.
        """
        for _ in range(SMTP_MAX_RETRIES + 1):
            try:
                with self._get_connection() as smtpconn:
                    failures = smtpconn.sendmail(recipients, msg)
                    if not failures:
                        # Sending successful!
                        return
                    else:
                        # At least one recipient was rejected by the server,
                        # but at least one recipient got it. Don't retry; raise
                        # exception so that we fail to client.
                        raise SendMailException(
                            'Sending to at least one recipent failed',
                            http_code=402,
                            failures=failures)
            except smtplib.SMTPException as err:
                self.log.error('Error sending', error=err, exc_info=True)

        self.log.error('Max retries reached; failing to client',
                       error=err)
        self._handle_sending_exception(err)

    def _handle_sending_exception(self, err):
        if isinstance(err, smtplib.SMTPServerDisconnected):
            raise SendMailException(
                'The server unexpectedly closed the connection', 503)

        elif isinstance(err, smtplib.SMTPRecipientsRefused):
            raise SendMailException('Sending to all recipients failed', 402)

        elif isinstance(err, smtplib.SMTPResponseException):
            # Distinguish between permanent failures due to message
            # content or recipients, and temporary failures for other reasons.
            # In particular, see https://support.google.com/a/answer/3726730
            if err.smtp_code == 550 and err.smtp_error.startswith('5.4.5'):
                message = 'Daily sending quota exceeded'
                http_code = 429
            elif (err.smtp_code == 552 and
                  (err.smtp_error.startswith('5.2.3') or
                   err.smtp_error.startswith('5.3.4'))):
                message = 'Message too large'
                http_code = 402
            elif err.smtp_code == 552 and err.smtp_error.startswith('5.7.0'):
                message = 'Message content rejected for security reasons'
                http_code = 402
            else:
                message = 'Sending failed'
                http_code = 503

            server_error = '{} : {}'.format(err.smtp_code, err.smtp_error)
            raise SendMailException(message, http_code=http_code,
                                    server_error=server_error)
        else:
            raise SendMailException('Sending failed', http_code=503,
                                    server_error=str(err))

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
        self._send(recipient_emails, msg)

        # Sent to all successfully
        self.log.info('Sending successful', sender=self.email_address,
                      recipients=recipient_emails)

    def _get_connection(self):
        smtp_connection = SMTPConnection(account_id=self.account_id,
                                         email_address=self.email_address,
                                         auth_type=self.auth_type,
                                         auth_token=self.auth_token,
                                         smtp_endpoint=self.smtp_endpoint,
                                         log=self.log)
        return smtp_connection
