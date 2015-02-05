import datetime
import getpass
from imapclient import IMAPClient
from socket import gaierror, error as socket_error
from ssl import SSLError

import sqlalchemy.orm.exc

from inbox.log import get_logger
log = get_logger()

from inbox.auth.base import AuthHandler
from inbox.basicauth import (ConnectionError, ValidationError,
                             TransientConnectionError,
                             UserRecoverableConfigError)
from inbox.models import Namespace
from inbox.models.backends.generic import GenericAccount

PROVIDER = 'generic'
AUTH_HANDLER_CLS = 'GenericAuthHandler'


class GenericAuthHandler(AuthHandler):
    def create_account(self, db_session, email_address, response):
        try:
            account = db_session.query(GenericAccount).filter_by(
                email_address=email_address).one()
        except sqlalchemy.orm.exc.NoResultFound:
            namespace = Namespace()
            account = GenericAccount(namespace=namespace)

        account.email_address = response['email']
        account.password = response['password']
        account.date = datetime.datetime.utcnow()

        provider_name = self.provider_name
        account.provider = provider_name
        if provider_name == 'custom':
            account.imap_endpoint = (response['imap_server_host'],
                                     response['imap_server_port'])
            account.smtp_endpoint = (response['smtp_server_host'],
                                     response['smtp_server_port'])

        # Hack to ensure that account syncs get restarted if they were stopped
        # because of e.g. invalid credentials and the user re-auths.
        # TODO(emfree): remove after status overhaul.
        if account.sync_state != 'running':
            account.sync_state = None

        return account

    def connect_account(self, email, credential, imap_endpoint,
                        account_id=None):
        """Provide a connection to a generic IMAP account.

        Raises
        ------
        ConnectionError
            If we cannot connect to the IMAP host.
        TransientConnectionError
            Sometimes the server bails out on us. Retrying may
            fix things.
        ValidationError
            If the credentials are invalid.
        """
        host, port = imap_endpoint
        try:
            conn = IMAPClient(host, port=port, use_uid=True, ssl=True)
        except IMAPClient.AbortError as e:
            log.error('account_connect_failed',
                      account_id=account_id,
                      email=email,
                      host=host,
                      port=port,
                      error="[ALERT] Can't connect to host - may be transient")
            raise TransientConnectionError(str(e))
        except(IMAPClient.Error, gaierror, socket_error) as e:
            log.error('account_connect_failed',
                      account_id=account_id,
                      email=email,
                      host=host,
                      port=port,
                      error='[ALERT] (Failure): {0}'.format(str(e)))
            raise ConnectionError(str(e))

        conn.debug = False
        try:
            conn.login(email, credential)
        except IMAPClient.AbortError as e:
            log.error('account_verify_failed',
                      account_id=account_id,
                      email=email,
                      host=host,
                      port=port,
                      error="[ALERT] Can't connect to host - may be transient")
            raise TransientConnectionError(str(e))
        except IMAPClient.Error as e:
            log.error('account_verify_failed',
                      account_id=account_id,
                      email=email,
                      host=host,
                      port=port,
                      error='[ALERT] Invalid credentials (Failure)')
            raise ValidationError(str(e))
        except SSLError as e:
            log.error('account_verify_failed',
                      account_id=account_id,
                      email=email,
                      host=host,
                      port=port,
                      error='[ALERT] SSL Connection error (Failure)')
            raise ConnectionError(str(e))

        return conn

    def _supports_condstore(self, conn):
        """Check if the connection supports CONDSTORE
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
        """Verifies a generic IMAP account by logging in and logging out.

        Note: Raises exceptions from connect_account() on error.

        Returns
        -------
        True: If the client can successfully connect.
        """
        conn = self.connect_account(account.email_address,
                                    account.password,
                                    account.imap_endpoint)
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
