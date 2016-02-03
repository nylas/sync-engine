import re
import ssl
import base64
import socket
import itertools

import smtplib

from nylas.logging import get_logger
log = get_logger()
from inbox.models.session import session_scope
from inbox.models.backends.imap import ImapAccount
from inbox.models.backends.oauth import token_manager as default_token_manager
from inbox.models.backends.gmail import g_token_manager
from inbox.models.backends.generic import GenericAccount
from inbox.sendmail.base import generate_attachments, SendMailException
from inbox.sendmail.message import create_email
from inbox.basicauth import OAuthError
from inbox.providers import provider_info
from inbox.util.blockstore import get_from_blockstore

# TODO[k]: Other types (LOGIN, XOAUTH, PLAIN-CLIENTTOKEN, CRAM-MD5)
AUTH_EXTNS = {'oauth2': 'XOAUTH2',
              'password': 'PLAIN'}

SMTP_MAX_RETRIES = 1
# Timeout in seconds for blocking operations. If no timeout is specified,
# attempts to, say, connect to the wrong port may hang forever.
SMTP_TIMEOUT = 45
SMTP_OVER_SSL_PORT = 465
SMTP_OVER_SSL_TEST_PORT = 64465

# Relevant protocol constants; see
# https://tools.ietf.org/html/rfc4954 and
# https://support.google.com/a/answer/3726730?hl=en
SMTP_AUTH_SUCCESS = 235
SMTP_AUTH_CHALLENGE = 334
SMTP_TEMP_AUTH_FAIL_CODES = (421, 454)


class _TokenManagerWrapper:

    def get_token(self, account, force_refresh=False):
        if account.provider == 'gmail':
            return g_token_manager.get_token_for_email(
                account, force_refresh=force_refresh)
        else:
            return default_token_manager.get_token(
                account, force_refresh=force_refresh)


token_manager = _TokenManagerWrapper()


class SMTP_SSL(smtplib.SMTP_SSL):
    """
        Derived class which correctly surfaces SMTP errors.
    """

    def rset(self):
        """Wrap rset() in order to correctly surface SMTP exceptions.
        SMTP.sendmail() does e.g.:
            # ...
            (code, resp) = self.data(msg)
            if code != 250:
                self.rset()
                raise SMTPDataError(code, resp)
            # ...
        But some servers will disconnect rather than respond to RSET, causing
        SMTPServerDisconnected rather than SMTPDataError to be raised. This
        basically obfuscates the actual server error.

        See also http://bugs.python.org/issue16005
        """
        try:
            smtplib.SMTP_SSL.rset(self)
        except smtplib.SMTPServerDisconnected:
            log.warning('Server disconnect during SMTP rset', exc_info=True)


class SMTP(smtplib.SMTP):
    """
        Derived class which correctly surfaces SMTP errors.
    """

    def rset(self):
        """Wrap rset() in order to correctly surface SMTP exceptions.
        SMTP.sendmail() does e.g.:
            # ...
            (code, resp) = self.data(msg)
            if code != 250:
                self.rset()
                raise SMTPDataError(code, resp)
            # ...
        But some servers will disconnect rather than respond to RSET, causing
        SMTPServerDisconnected rather than SMTPDataError to be raised. This
        basically obfuscates the actual server error.

        See also http://bugs.python.org/issue16005
        """
        try:
            smtplib.SMTP.rset(self)
        except smtplib.SMTPServerDisconnected:
            log.warning('Server disconnect during SMTP rset', exc_info=True)


def _transform_ssl_error(strerror):
    """ Clean up errors like:

    _ssl.c:510: error:14090086:SSL routines:SSL3_GET_SERVER_CERTIFICATE:certificate verify failed  # noqa
    """
    if strerror.endswith('certificate verify failed'):
        return 'SMTP server SSL certificate verify failed'
    else:
        return strerror


class SMTPConnection(object):

    def __init__(self, account_id, email_address, smtp_username,
                 auth_type, auth_token, smtp_endpoint, log):
        self.account_id = account_id
        self.email_address = email_address
        self.smtp_username = smtp_username
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

    def _connect(self, host, port):
        """ Connect, with error-handling """
        try:
            self.connection.connect(host, port)
        except socket.error as e:
            # 'Connection refused', SSL errors for non-TLS connections, etc.
            msg = _transform_ssl_error(e.strerror)
            raise SendMailException(msg, 503)

    def setup(self):
        host, port = self.smtp_endpoint
        if port in (SMTP_OVER_SSL_PORT, SMTP_OVER_SSL_TEST_PORT):
            self.connection = SMTP_SSL(timeout=SMTP_TIMEOUT)
            self._connect(host, port)
        else:
            self.connection = SMTP(timeout=SMTP_TIMEOUT)
            self._connect(host, port)
            # Put the SMTP connection in TLS mode
            self.connection.ehlo()
            if not self.connection.has_extn('starttls'):
                raise SendMailException('Required SMTP STARTTLS not '
                                        'supported.', 403)
            try:
                self.connection.starttls()
            except ssl.SSLError as e:
                msg = _transform_ssl_error(e.strerror)
                raise SendMailException(msg, 503)

        # Auth the connection
        self.connection.ehlo()
        auth_handler = self.auth_handlers.get(self.auth_type)
        auth_handler()

    # OAuth2 authentication
    def _smtp_oauth2_try_refresh(self):
        with session_scope(self.account_id) as db_session:
            account = db_session.query(ImapAccount).get(self.account_id)
            self.auth_token = token_manager.get_token(
                account, force_refresh=True)

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
        if code in SMTP_TEMP_AUTH_FAIL_CODES and resp.startswith('4.7.0'):
            # If we're getting 'too many login attempt errors', tell the client
            # they are being rate-limited.
            raise SendMailException('Temporary provider send throttling',
                                    429)

        if code != SMTP_AUTH_SUCCESS:
            # If auth failed for any other reason, try to refresh the access
            # token and try again.
            self._smtp_oauth2_try_refresh()
            code, resp = self._try_xoauth2()
            if code != SMTP_AUTH_SUCCESS:
                raise SendMailException(
                    'Could not authenticate with the SMTP server.', 403)
        self.log.info('SMTP Auth(OAuth2) success',
                      email_address=self.email_address)

    # Password authentication
    def smtp_password(self):
        c = self.connection

        try:
            c.login(self.smtp_username, self.auth_token)
        except smtplib.SMTPAuthenticationError as e:
            self.log.error('SMTP login refused', exc=e)
            raise SendMailException(
                'Could not authenticate with the SMTP server.', 403)
        except smtplib.SMTPException as e:
            # Raised by smtplib if the server doesn't support the AUTH
            # extension or doesn't support any of the implemented mechanisms.
            # Shouldn't really happen normally.
            self.log.error('SMTP auth failed due to unsupported mechanism',
                           exc=e)
            raise SendMailException(str(e), 403)

        self.log.info('SMTP Auth(Password) success')

    def sendmail(self, recipients, msg):
        try:
            return self.connection.sendmail(
                self.email_address, recipients, msg)
        except UnicodeEncodeError:
            self.log.error('Unicode error when trying to decode email',
                           logstash_tag='sendmail_encode_error',
                           email=self.email_address, recipients=recipients)
            raise SendMailException(
                'Invalid character in recipient address', 402)


class SMTPClient(object):
    """ SMTPClient for Gmail and other IMAP providers. """

    def __init__(self, account):
        self.account_id = account.id
        self.log = get_logger()
        self.log.bind(account_id=account.id)
        if isinstance(account, GenericAccount):
            self.smtp_username = account.smtp_username
        else:
            # non-generic accounts have no smtp username
            self.smtp_username = account.email_address
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
            if isinstance(account, GenericAccount):
                self.auth_token = account.smtp_password
            else:
                # non-generic accounts have no smtp password
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
                            http_code=200,
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

    def send_generated_email(self, recipients, raw_message):
        # A tiny wrapper over _send because the API differs
        # between SMTP and EAS.
        return self._send(recipients, raw_message)

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
        # @emfree - 3/19/2015
        #
        # Note that we intentionally don't set the Bcc header in the message we
        # construct, because this would would result in a MIME message being
        # generated with a Bcc header which all recipients can see.
        #
        # Arguably we should send each Bcc'ed recipient a MIME message that has
        # a Bcc: <only them> header. This is what the Gmail web UI appears to
        # do. However, this would need to be carefully implemented and tested.
        # The current approach was chosen for its comparative simplicity. I'm
        # pretty sure that other clients do it this way as well. It is the
        # first of the three implementations described here:
        # http://tools.ietf.org/html/rfc2822#section-3.6.3
        #
        # Note that we ensure in our SMTP code BCCed recipients still actually
        # get the message.

        # from_addr is only ever a list with one element
        from_addr = draft.from_addr[0]
        msg = create_email(from_name=from_addr[0],
                           from_email=from_addr[1],
                           reply_to=draft.reply_to,
                           inbox_uid=draft.inbox_uid,
                           to_addr=draft.to_addr,
                           cc_addr=draft.cc_addr,
                           bcc_addr=None,
                           subject=draft.subject,
                           html=draft.body,
                           in_reply_to=draft.in_reply_to,
                           references=draft.references,
                           attachments=attachments)

        recipient_emails = [email for name, email in itertools.chain(
            draft.to_addr, draft.cc_addr, draft.bcc_addr)]
        self._send(recipient_emails, msg)

        # Sent to all successfully
        self.log.info('Sending successful', sender=from_addr[1],
                      recipients=recipient_emails)

    def send_raw(self, msg):
        recipient_emails = [email for name, email in itertools.chain(
            msg.bcc_addr, msg.cc_addr, msg.to_addr)]

        raw_message = get_from_blockstore(msg.data_sha256)
        mime_body = re.sub(r'Bcc: [^\r\n]*\r\n', '', raw_message)
        self._send(recipient_emails, mime_body)

        # Sent to all successfully
        sender_email = msg.from_addr[0][1]
        self.log.info('Sending successful', sender=sender_email,
                      recipients=recipient_emails)

    def _get_connection(self):
        smtp_connection = SMTPConnection(account_id=self.account_id,
                                         email_address=self.email_address,
                                         smtp_username=self.smtp_username,
                                         auth_type=self.auth_type,
                                         auth_token=self.auth_token,
                                         smtp_endpoint=self.smtp_endpoint,
                                         log=self.log)
        return smtp_connection
