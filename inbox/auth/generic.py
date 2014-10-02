import datetime
import time
from imapclient import IMAPClient
from socket import gaierror, error as socket_error
from ssl import SSLError

import sqlalchemy.orm.exc

from inbox.log import get_logger
log = get_logger()

from inbox.basicauth import password_auth
from inbox.basicauth import (ConnectionError, ValidationError,
                             TransientConnectionError)
from inbox.models import Namespace
from inbox.models.backends.generic import GenericAccount
from inbox.models.account import Account
from inbox.providers import provider_info
from inbox.util.url import provider_from_address
from inbox.basicauth import NotSupportedError

PROVIDER = 'generic'


def create_auth_account(db_session, email_address, token, exit):
    response = auth_account(email_address, token, exit)
    account = create_account(db_session, email_address, response)

    return account


def auth_account(email_address, token, exit):
    return password_auth(email_address, token, exit)


def create_account(db_session, email_address, response):
    provider_name = provider_from_address(email_address)
    if provider_name == "unknown":
        raise NotSupportedError('Inbox does not support the email provider.')

    try:
        account = db_session.query(GenericAccount).filter_by(
            email_address=email_address).one()
    except sqlalchemy.orm.exc.NoResultFound:
        namespace = Namespace()
        account = GenericAccount(namespace=namespace)

    account.email_address = response['email']
    account.password = response['password']
    account.date = datetime.datetime.utcnow()
    account.provider = provider_name

    return account


def delete_account(db_session, email_address):
    try:
        account = db_session.query(Account).filter_by(
            email_address=email_address).one()
    except sqlalchemy.orm.exc.NoResultFound:
        return  # The account doesn't exist, no need to delete it

    # We must stop the sync before removing the account
    # FIXME: handle race conditions.
    account.stop_sync()
    db_session.commit()
    while True:
        time.sleep(10)
        if account.sync_status['sync_end_time'] is not None:
            break

    db_session.delete(account)  # Note: this _must_ be a soft delete
    db_session.delete(account.namespace)
    db_session.commit()


def connect_account(provider, email, credential):
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

    info = provider_info(provider)
    host, port = info['imap']
    try:
        conn = IMAPClient(host, port=port, use_uid=True, ssl=True)
    except IMAPClient.AbortError as e:
        log.error('account_connect_failed',
                  email=email,
                  host=host,
                  port=port,
                  error=("[ALERT] Can't connect to host - may be transient"))
        raise TransientConnectionError(str(e))
    except(IMAPClient.Error, gaierror, socket_error) as e:
        log.error('account_connect_failed',
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
                  email=email,
                  host=host,
                  port=port,
                  error="[ALERT] Can't connect to host - may be transient")
        raise TransientConnectionError(str(e))
    except IMAPClient.Error as e:
        log.error('account_verify_failed',
                  email=email,
                  host=host,
                  port=port,
                  error='[ALERT] Invalid credentials (Failure)')
        raise ValidationError(str(e))
    except SSLError as e:
        log.error('account_verify_failed',
                  email=email,
                  host=host,
                  port=port,
                  error='[ALERT] SSL Connection error (Failure)')
        raise ConnectionError(str(e))

    return conn


def supports_condstore(conn):
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


def verify_account(account):
    """Verifies a generic IMAP account by logging in and logging out.

    Note: Raises exceptions from connect_account() on error.

    Returns
    -------
    True: If the client can successfully connect.
    """
    conn = connect_account(account.provider,
                           account.email_address,
                           account.password)

    info = provider_info(account.provider)
    if "condstore" not in info:
        if supports_condstore(conn):
            account.supports_condstore = True

    conn.logout()
    return True
