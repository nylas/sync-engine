from imapclient import IMAPClient

from socket import gaierror, error as socket_error
from ssl import SSLError
from inbox.providers import provider_info
from inbox.basicauth import (ConnectionError, ValidationError,
                             TransientConnectionError)
from inbox.log import get_logger
log = get_logger()


def connect_account(account):
    """Provide a connection to a IMAP account.

    Raises
    ------
    socket.error
        If we cannot connect to the IMAP host.
    IMAPClient.error
        If the credentials are invalid.
    """
    info = provider_info(account.provider)
    host = info['imap']
    try:
        conn = IMAPClient(host, use_uid=True, ssl=True)
    except IMAPClient.AbortError as e:
        log.error('account_connect_failed',
                  email=account.email_address,
                  host=host,
                  error=("[ALERT] Can't connect to host - may be transient"))
        raise TransientConnectionError(str(e))
    except(IMAPClient.Error, gaierror, socket_error) as e:
        log.error('account_connect_failed',
                  email=account.email_address,
                  host=host,
                  error='[ALERT] (Failure): {0}'.format(str(e)))
        raise ConnectionError(str(e))

    conn.debug = False
    try:
        conn.oauth2_login(account.email_address, account.access_token)
    except IMAPClient.AbortError as e:
        log.error('account_verify_failed',
                  email=account.email_address,
                  host=host,
                  error="[ALERT] Can't connect to host - may be transient")
        raise TransientConnectionError(str(e))
    except IMAPClient.Error as e:
        log.error('IMAP Login error during refresh auth token. '
                  'Account: {}, error: {}'.format(account.email_address, e))
        if str(e) == '[ALERT] Invalid credentials (Failure)':
            # Access token could've expired
            try:
                conn.oauth2_login(account.email_address,
                                  account.renew_access_token())
            except IMAPClient.Error as e:
                raise ValidationError(str(e))
        else:
            raise ConnectionError(str(e))
    except SSLError as e:
        log.error('account_verify_failed',
                  email=account.email_address,
                  host=host,
                  error='[ALERT] (Failure) SSL Connection error')
        raise ConnectionError(str(e))

    return conn


def verify_account(account):
    """Verifies a IMAP account by logging in."""
    conn = connect_account(account)
    conn.logout()
    return True
