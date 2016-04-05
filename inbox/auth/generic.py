import datetime
import getpass
from backports import ssl
from imapclient import IMAPClient
import socket

from nylas.logging import get_logger
log = get_logger()

from inbox.auth.base import AuthHandler, account_or_none
from inbox.basicauth import (ValidationError, UserRecoverableConfigError,
                             SSLNotSupportedError, SettingUpdateError)
from inbox.models import Namespace
from inbox.models.backends.generic import GenericAccount
from inbox.sendmail.smtp.postel import SMTPClient
from inbox.util.url import matching_subdomains

PROVIDER = 'generic'
AUTH_HANDLER_CLS = 'GenericAuthHandler'

_ossl = ssl.ossl


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

        # The server endpoints can ONLY be set at account creation and
        # CANNOT be subsequently changed in order to prevent MITM attacks.
        account.provider = self.provider_name
        if self.provider_name == 'custom':
            account.imap_endpoint = (response['imap_server_host'],
                                     response['imap_server_port'])
            account.smtp_endpoint = (response['smtp_server_host'],
                                     response['smtp_server_port'])

        # Shim for back-compatability with legacy auth
        # The old API does NOT send these but authentication now uses them
        # so set them (included here, set in update_account()).
        for username in ['imap_username', 'smtp_username']:
            if username not in response:
                response[username] = email_address
        for password in ['imap_password', 'smtp_password']:
            if password not in response:
                response[password] = response['password']

        return self.update_account(account, response)

    def update_account(self, account, response):
        account.email_address = response['email']
        for attribute in ['name', 'imap_username', 'imap_password',
                          'smtp_username', 'smtp_password', 'password']:
            if response.get(attribute):
                setattr(account, attribute, response[attribute])

        # Shim for back-compatability with legacy auth
        if response.get('imap_password'):
            # The new API sends separate IMAP/ SMTP credentials but we need to
            # set the legacy password attribute.
            # TODO[k]: Remove once column in dropped.
            account.password = response['imap_password']
        else:
            # The old API does NOT send these but authentication now uses them
            # so update them.
            for attr in ('imap_username', 'smtp_username'):
                if attr not in response:
                    setattr(account, attr, response['email'])
            for attr in ('imap_password', 'smtp_password'):
                if attr not in response:
                    setattr(account, attr, response['password'])

        account.date = datetime.datetime.utcnow()

        if self.provider_name == 'custom':
            for attribute in ('imap_server_host', 'smtp_server_host'):
                old_value = getattr(account, '_{}'.format(attribute), None)
                new_value = response.get(attribute)
                if (new_value and old_value and new_value != old_value):
                    # Before updating the domain name, check if:
                    # 1/ they have the same parent domain
                    # 2/ they direct to the same IP.
                    if not matching_subdomains(new_value, old_value):
                        raise SettingUpdateError(
                            "Updating the IMAP/SMTP servers is not permitted. Please "
                            "verify that the server names you entered are correct. "
                            "If your IMAP/SMTP server has in fact changed, please "
                            "contact Nylas support to update it. More details here: "
                            "https://support.nylas.com/hc/en-us/articles/218006767")

                    # If all those conditions are met, update the address.
                    setattr(account, '_{}'.format(attribute), new_value)

        account.ssl_required = response.get('ssl_required', True)

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
        ssl_required = account.ssl_required
        try:
            conn = create_imap_connection(host, port, ssl_required)
        except (IMAPClient.Error, socket.error) as exc:
            log.error('Error instantiating IMAP connection',
                      account_id=account.id,
                      email=account.email_address,
                      host=host,
                      port=port,
                      ssl_required=ssl_required,
                      error=exc)
            raise
        try:
            conn.login(account.imap_username, account.imap_password)
        except IMAPClient.Error as exc:
            if _auth_is_invalid(exc):
                log.error('IMAP login failed',
                          account_id=account.id,
                          email=account.email_address,
                          host=host, port=port,
                          ssl_required=ssl_required,
                          error=exc)
                raise ValidationError(exc)
            else:
                log.error('IMAP login failed for an unknown reason',
                          account_id=account.id,
                          email=account.email_address,
                          host=host,
                          port=port,
                          ssl_required=ssl_required,
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
                            ssl_required=ssl_required,
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
        Verifies a generic IMAP account by logging in and logging out to both
        the IMAP/ SMTP servers.

        Note:
        Raises exceptions from connect_account(), SMTPClient._get_connection()
        on error.

        Returns
        -------
        True: If the client can successfully connect to both.

        """
        # Verify IMAP login
        conn = self.connect_account(account)

        info = account.provider_info
        if "condstore" not in info:
            if self._supports_condstore(conn):
                account.supports_condstore = True
        try:
            conn.list_folders()

            folder_prefix, folder_separator = conn.namespace()[0][0]
            account.folder_separator = folder_separator
            account.folder_prefix = folder_prefix
        except Exception as e:
            log.error("account_folder_list_failed",
                      email=account.email_address,
                      account_id=account.id,
                      error=e.message)
            error_message = ("Full IMAP support is not enabled for this account. "
                             "Please contact your domain "
                             "administrator and try again.")
            raise UserRecoverableConfigError(error_message)
        finally:
            conn.logout()

        # Verify SMTP login
        try:
            # Check that SMTP settings work by establishing and closing and
            # SMTP session.
            smtp_client = SMTPClient(account)
            with smtp_client._get_connection():
                pass
        except socket.gaierror as exc:
            log.error('Failed to resolve SMTP server domain',
                      email=account.email_address,
                      account_id=account.id,
                      error=exc)
            error_message = ("Couldn't resolve the SMTP server domain name. "
                             "Please check that your SMTP settings are correct.")
            raise UserRecoverableConfigError(error_message)

        except socket.timeout as exc:
            log.error('TCP timeout when connecting to SMTP server',
                      email=account.email_address,
                      account_id=account.id,
                      error=exc)

            error_message = ("Connection timeout when connecting to SMTP server. "
                             "Please check that your SMTP settings are correct.")
            raise UserRecoverableConfigError(error_message)

        except Exception as exc:
            log.error('Failed to establish an SMTP connection',
                      email=account.email_address,
                      smtp_endpoint=account.smtp_endpoint,
                      account_id=account.id,
                      error=exc)
            raise UserRecoverableConfigError("Please check that your SMTP "
                                             "settings are correct.")

        # Reset the sync_state to 'running' on a successful re-auth.
        # Necessary for API requests to proceed and an account modify delta to
        # be returned to delta/ streaming clients.
        # NOTE: Setting this does not restart the sync. Sync scheduling occurs
        # via the sync_should_run bit (set to True in update_account() above).
        account.sync_state = ('running' if account.sync_state else
                              account.sync_state)
        return True

    def interactive_auth(self, email_address):
        response = dict(email=email_address)

        if self.provider_name == 'custom':
            imap_server_host = raw_input('IMAP server host: ').strip()
            imap_server_port = raw_input('IMAP server port: ').strip() or 993
            imap_um = 'IMAP username (empty for same as email address): '
            imap_user = raw_input(imap_um).strip() or email_address
            imap_pwm = 'IMAP password for {0}: '
            imap_p = getpass.getpass(imap_pwm.format(email_address))

            smtp_server_host = raw_input('SMTP server host: ').strip()
            smtp_server_port = raw_input('SMTP server port: ').strip() or 587
            smtp_um = 'SMTP username (empty for same as email address): '
            smtp_user = raw_input(smtp_um).strip() or email_address
            smtp_pwm = 'SMTP password for {0} (empty for same as IMAP): '
            smtp_p = getpass.getpass(smtp_pwm.format(email_address)) or imap_p

            ssl_required = raw_input('Require SSL? [Y/n] ').strip().\
                lower() != 'n'

            response.update(imap_server_host=imap_server_host,
                            imap_server_port=imap_server_port,
                            imap_username=imap_user,
                            imap_password=imap_p,
                            smtp_server_host=smtp_server_host,
                            smtp_server_port=smtp_server_port,
                            smtp_username=smtp_user,
                            smtp_password=smtp_p,
                            ssl_required=ssl_required)
        else:
            password_message = 'Password for {0} (hidden): '
            pw = ''
            while not pw:
                pw = getpass.getpass(password_message.format(email_address))
            response.update(password=pw)

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
        '[auth] authentication failed.',
        'invalid login credentials',
        '[ALERT] Please log in via your web browser',
    )
    return any(exc.message.lower().startswith(msg) for msg in
               AUTH_INVALID_PREFIXES)


def create_imap_connection(host, port, ssl_required):
    """
    Return a connection to the IMAP server.
    The connection is encrypted if the specified port is the default IMAP
    SSL port (993) or the server supports STARTTLS.
    IFF neither condition is met and SSL is not required, an insecure connection
    is returned. Otherwise, an exception is raised.

    """
    use_ssl = port == 993

    # TODO: certificate pinning for well known sites
    context = create_default_context()
    conn = IMAPClient(host, port=port, use_uid=True,
                      ssl=use_ssl, ssl_context=context, timeout=120)

    if not use_ssl:
        # If STARTTLS is available, always use it. If it's not/ it fails, use
        # `ssl_required` to determine whether to fail or continue with
        # plaintext authentication.
        if conn.has_capability('STARTTLS'):
            try:
                conn.starttls(context)
            except Exception:
                if not ssl_required:
                    log.warning('STARTTLS supported but failed for SSL NOT '
                                'required authentication', exc_info=True)
                else:
                    raise
        elif ssl_required:
            raise SSLNotSupportedError('Required IMAP STARTTLS not supported.')

    return conn


def create_default_context():
    """
    Return a backports.ssl.SSLContext object configured with sensible
    default settings. This was adapted from imapclient.create_default_context
    to allow all ciphers and disable certificate verification.

    """
    # adapted from Python 3.4's ssl.create_default_context

    context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)

    # do not verify that certificate is signed nor that the
    # certificate matches the hostname
    context.verify_mode = ssl.CERT_NONE
    context.check_hostname = False

    # SSLv2 considered harmful.
    context.options |= _ossl.OP_NO_SSLv2

    # SSLv3 has problematic security and is only required for really old
    # clients such as IE6 on Windows XP
    context.options |= _ossl.OP_NO_SSLv3

    # disable compression to prevent CRIME attacks (OpenSSL 1.0+)
    context.options |= getattr(_ossl, "OP_NO_COMPRESSION", 0)

    # Prefer the server's ciphers by default so that we get stronger
    # encryption
    context.options |= getattr(_ossl, "OP_CIPHER_SERVER_PREFERENCE", 0)

    # Use single use keys in order to improve forward secrecy
    context.options |= getattr(_ossl, "OP_SINGLE_DH_USE", 0)
    context.options |= getattr(_ossl, "OP_SINGLE_ECDH_USE", 0)

    return context
