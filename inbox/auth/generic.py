import datetime
from imapclient import IMAPClient
from socket import gaierror, error as socket_error
from ssl import SSLError

import sqlalchemy.orm.exc

from inbox.log import get_logger
log = get_logger()

from inbox.basicauth import password_auth
from inbox.basicauth import ConnectionError, ValidationError
from inbox.models import Namespace
from inbox.models.backends.generic import GenericAccount
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


def connect_account(account):
    """Provide a connection to a generic IMAP account.

    Raises
    ------
    ConnectionError
        If we cannot connect to the IMAP host.
    ValidationError
        If the credentials are invalid.
    """

    info = provider_info(account.provider)
    host = info["imap"]
    try:
        conn = IMAPClient(host, use_uid=True, ssl=True)
    except IMAPClient.Error as e:
        log.error('account_connect_failed',
                  host=host,
                  error="[ALERT] Can't connect to host (Failure)")
        raise ConnectionError(str(e))
    except gaierror as e:
        log.error('account_connect_failed',
                  host=host,
                  error="[ALERT] Name resolution faiure (Failure)")
        raise ConnectionError(str(e))
    except socket_error as e:
        log.error('account_connect_failed',
                  host=host,
                  error="[ALERT] Socket connection failure (Failure)")
        raise ConnectionError(str(e))

    conn.debug = False
    try:
        conn.login(account.email_address, account.password)
    except IMAPClient.Error as e:
        log.error('account_verify_failed',
                  email=account.email_address,
                  host=host,
                  error="[ALERT] Invalid credentials (Failure)")
        raise ValidationError()
    except SSLError as e:
        log.error('account_verify_failed',
                  email=account.email_address,
                  host=host,
                  error="[ALERT] SSL Connection error (Failure)")
        raise ConnectionError(str(e))

    return conn


def verify_account(account):
    """Verifies a generic IMAP account by logging in and logging out.

    Note: Raises exceptions from connect_account() on error.

    Returns
    -------
    True: If the client can successfully connect.
    """
    conn = connect_account(account)
    conn.logout()
    return True
