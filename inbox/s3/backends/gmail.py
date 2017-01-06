import base64
import requests
from inbox.s3.exc import TemporaryEmailFetchException, EmailDeletedException
from inbox.auth.oauth import OAuthRequestsWrapper
from inbox.models.backends.gmail import g_token_manager
from nylas.logging import get_logger
log = get_logger()


# We use the Google API so we don't have to worry about
# the Gmail max IMAP connection limit.
def get_gmail_raw_contents(message):
    account = message.namespace.account
    auth_token = g_token_manager.get_token_for_email(account)

    # The Gmail API exposes the X-GM-MSGID field but encodes it
    # in hexadecimal.
    g_msgid = message.g_msgid

    if g_msgid is None:
        raise EmailDeletedException("Couldn't find message on backend server. This is a permanent error.")

    if isinstance(g_msgid, basestring):
        g_msgid = int(g_msgid)

    hex_id = format(g_msgid, 'x')
    url = 'https://www.googleapis.com/gmail/v1/users/me/messages/{}?format=raw'.format(hex_id, 'x')
    r = requests.get(url, auth=OAuthRequestsWrapper(auth_token))

    if r.status_code != 200:
        log.error('Got an error when fetching raw email', r.status_code, r.text)

    if r.status_code in [403, 429]:
        raise TemporaryEmailFetchException("Temporary usage limit hit. Please try again.")
    if r.status_code == 404:
        raise EmailDeletedException("Couldn't find message on backend server. This is a permanent error.")
    elif r.status_code >= 500 and r.status_code <= 599:
        raise TemporaryEmailFetchException("Backend server error. Please try again in a few minutes.")

    data = r.json()
    raw = str(data['raw'])
    return base64.urlsafe_b64decode(raw + '=' * (4 - len(raw) % 4))
