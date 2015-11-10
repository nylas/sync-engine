import datetime
import getpass
from backports import ssl
from imapclient import IMAPClient, create_default_context
import socket

from nylas.logging import get_logger
log = get_logger()

from inbox.auth.base import AuthHandler, account_or_none
from inbox.basicauth import ValidationError, UserRecoverableConfigError
from inbox.models import Namespace
from inbox.models.backends.generic import GenericAccount
from inbox.sendmail.smtp.postel import SMTPClient


PROVIDER = 'generic'
AUTH_HANDLER_CLS = 'GenericAuthHandler'


class GenericAuthHandler(AuthHandler):

    def get_account(self, target, email_address, response):
        account = account_or_none(target, GenericAccount, email_address)
        if not account:
            account = self.create_account(email_address, response)
        account = self.update_account(account, response)
        return account

    def create_account(self, email_address, response):
        # This method assumes that the existence of an account for the
        # provider and email_address has been checked by the caller;
        # callers may have different methods of performing the check
        # (redwood auth versus get_account())
        namespace = Namespace()
        account = GenericAccount(namespace=namespace)
        return self.update_account(account, response)

    def update_account(self, account, response):
        account.email_address = response['email']
        if response.get('name'):
            account.name = response['name']
        account.password = response['password']
        account.date = datetime.datetime.utcnow()
        provider_name = self.provider_name
        account.provider = provider_name
        if provider_name == 'custom':
            account.imap_endpoint = (response['imap_server_host'],
                                     response['imap_server_port'])
            account.smtp_endpoint = (response['smtp_server_host'],
                                     response['smtp_server_port'])
        # Ensure account has sync enabled after authing.
        account.enable_sync()
        return account

    def connect_account(self, account):
        """
        Returns an authenticated IMAP connection for the given account.

        Raises
        ------
        ValidationError
            If IMAP LOGIN failed because of invalid username/password
        imapclient.IMAPClient.Error, socket.error
            If other errors occurred establishing the connection or logging in.

        """
        host, port = account.imap_endpoint
        try:
            conn = create_imap_connection(host, port)
        except (IMAPClient.Error, socket.error) as exc:
            log.error('Error instantiating IMAP connection',
                      account_id=account.id,
                      email=account.email_address,
                      host=host,
                      port=port,
                      error=exc)
            raise

        try:
            conn.login(account.email_address, account.password)
        except IMAPClient.Error as exc:
            if _auth_is_invalid(exc):
                log.error('IMAP login failed',
                          account_id=account.id,
                          email=account.email_address,
                          host=host, port=port,
                          error=exc)
                raise ValidationError(exc)
            else:
                log.error('IMAP login failed for an unknown reason',
                          account_id=account.id,
                          email=account.email_address,
                          host=host,
                          port=port,
                          error=exc)
                raise

        if 'ID' in conn.capabilities():
            # Try to issue an IMAP ID command. Some whacky servers
            # (163.com) require this, but it's an encouraged practice in any
            # case. Since this isn't integral to the sync in general, don't
            # fail if there are any errors.
            # (Note that as of May 2015, this depends on a patched imapclient
            # that implements the ID command.)
            try:
                conn.id_({'name': 'Nylas Sync Engine', 'vendor': 'Nylas',
                          'contact': 'support@nylas.com'})
            except Exception as exc:
                log.warning('Error issuing IMAP ID command; continuing',
                            account_id=account.id,
                            email=account.email_address,
                            host=host,
                            port=port,
                            error=exc)

        return conn

    def _supports_condstore(self, conn):
        """
        Check if the connection supports CONDSTORE

        Returns
        -------
        True: If the account supports CONDSTORE
        False otherwise

        """
        capabilities = conn.capabilities()
        if "CONDSTORE" in capabilities:
            return True

        return False

    def verify_account(self, account):
        """
        Verifies a generic IMAP account by logging in and logging out.

        Note: Raises exceptions from connect_account() on error.

        Returns
        -------
        True: If the client can successfully connect.

        """
        conn = self.connect_account(account)
        info = account.provider_info
        if "condstore" not in info:
            if self._supports_condstore(conn):
                account.supports_condstore = True
        try:
            conn.list_folders()
        except Exception as e:
            log.error("account_folder_list_failed",
                      email=account.email_address,
                      account_id=account.id,
                      error=e.message)
            raise UserRecoverableConfigError("Full IMAP support is not "
                                             "enabled for this account. "
                                             "Please contact your domain "
                                             "administrator and try again.")
        finally:
            conn.logout()
        try:
            # Check that SMTP settings work by establishing and closing and
            # SMTP session.
            smtp_client = SMTPClient(account)
            with smtp_client._get_connection():
                pass
        except Exception as exc:
            log.error('Failed to establish an SMTP connection',
                      email=account.email_address,
                      account_id=account.id,
                      error=exc)
            raise UserRecoverableConfigError("Please check that your SMTP "
                                             "settings are correct.")
        return True

    def interactive_auth(self, email_address):
        password_message = 'Password for {0} (hidden): '
        pw = ''
        while not pw:
            pw = getpass.getpass(password_message.format(email_address))

        response = dict(email=email_address, password=pw)

        if self.provider_name == 'custom':
            imap_server_host = raw_input('IMAP server host: ').strip()
            imap_server_port = raw_input('IMAP server port: ').strip() or 993
            smtp_server_host = raw_input('SMTP server host: ').strip()
            smtp_server_port = raw_input('SMTP server port: ').strip() or 587
            response.update(imap_server_host=imap_server_host,
                            imap_server_port=imap_server_port,
                            smtp_server_host=smtp_server_host,
                            smtp_server_port=smtp_server_port)

        return response


def _auth_is_invalid(exc):
    # IMAP doesn't really have error semantics, so we have to match the error
    # message against a list of known response strings to determine whether we
    # couldn't log in because the credentials are invalid, or because of some
    # temporary server error.
    AUTH_INVALID_PREFIXES = (
        '[authenticationfailed]',
        'incorrect username or password',
        'login failed',
        'invalid login or password',
        'login login error password error',
        '[auth] authentication failed.'
    )
    return any(exc.message.lower().startswith(msg) for msg in
               AUTH_INVALID_PREFIXES)


def create_imap_connection(host, port):
    use_ssl = port == 993

    # TODO: certificate pinning for well known sites
    context = create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    conn = IMAPClient(host, port=port, use_uid=True,
                      ssl=use_ssl, ssl_context=context)
    if not use_ssl:
        # Raises an exception if TLS can't be established
        conn.starttls(context)
    return conn
