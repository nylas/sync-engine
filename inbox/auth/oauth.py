from imapclient import IMAPClient

from inbox.basicauth import ConnectionError, ValidationError
from inbox.log import get_logger
log = get_logger()


def connect_account(account, host):
    """Provide a connection to a IMAP account.

    Raises
    ------
    socket.error
        If we cannot connect to the IMAP host.
    IMAPClient.error
        If the credentials are invalid.
    """

    try:
        conn = IMAPClient(host, use_uid=True, ssl=True)
    except IMAPClient.Error as e:
        log.error('account_connect_failed',
                  host=host,
                  error="[ALERT] Can't connect to host (Failure)")
        raise ConnectionError(str(e))

    conn.debug = False
    try:
        conn.oauth2_login(account.email_address, account.access_token)
    except IMAPClient.Error as e:
        log.error("IMAP Login error, refresh auth token for: {}"
                  .format(account.email_address))
        log.error("Error was: {}".format(e))
        if str(e) == '[ALERT] Invalid credentials (Failure)':
            # maybe the access token expired?
            try:
                conn.oauth2_login(account.email_address,
                                  account.renew_access_token())
            except IMAPClient.Error as e:
                raise ValidationError()
        else:
            raise ValidationError()

    return conn


def verify_account(account, host):
    """Verifies a IMAP account by logging in."""
    conn = connect_account(account, host)
    conn.logout()
    return True
