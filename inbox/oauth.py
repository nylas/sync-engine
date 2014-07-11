import urllib
import requests
from requests import ConnectionError

from inbox.util.url import url_concat
from inbox.log import get_logger
log = get_logger()
from inbox.config import config
from inbox.basicauth import AuthError

# Google OAuth app credentials
GOOGLE_OAUTH_CLIENT_ID = config.get_required('GOOGLE_OAUTH_CLIENT_ID')
GOOGLE_OAUTH_CLIENT_SECRET = config.get_required('GOOGLE_OAUTH_CLIENT_SECRET')
REDIRECT_URI = config.get_required('GOOGLE_OAUTH_REDIRECT_URI')

OAUTH_AUTHENTICATE_URL = 'https://accounts.google.com/o/oauth2/auth'
OAUTH_ACCESS_TOKEN_URL = 'https://accounts.google.com/o/oauth2/token'
OAUTH_TOKEN_VALIDATION_URL = 'https://www.googleapis.com/oauth2/v1/tokeninfo'
USER_INFO_URL = 'https://www.googleapis.com/oauth2/v1/userinfo'

OAUTH_SCOPE = ' '.join([
    'https://www.googleapis.com/auth/userinfo.email',  # email address
    'https://www.googleapis.com/auth/userinfo.profile',  # G+ profile
    'https://mail.google.com/',  # email
    'https://www.google.com/m8/feeds',  # contacts
    'https://www.googleapis.com/auth/calendar'  # calendar
])


class OAuthError(AuthError):
    pass


class InvalidOAuthGrantError(OAuthError):
    pass


def validate_token(access_token):
    """ Helper function which will validate an access token. """
    log.info('Validating oauth token...')
    try:
        response = requests.get(OAUTH_TOKEN_VALIDATION_URL +
                                '?access_token=' + access_token)
    except ConnectionError, e:
        log.error('Validation failed.')
        log.error(e)
        return None  # TODO better error handling here

    validation_dict = response.json()

    if 'error' in validation_dict:
        assert validation_dict['error'] == 'invalid_token'
        log.error('{0} - {1}'.format(validation_dict['error'],
                                     validation_dict['error_description']))
        return None

    return validation_dict


def new_token(refresh_token):
    """ Helper function which gets a new access token from a refresh token."""
    assert refresh_token is not None, 'refresh_token required'

    log.info('acquiring_new_oauth_token')
    args = {
        'refresh_token': refresh_token,
        'client_id': GOOGLE_OAUTH_CLIENT_ID,
        'client_secret': GOOGLE_OAUTH_CLIENT_SECRET,
        'grant_type': 'refresh_token'
    }

    try:
        headers = {'Content-type': 'application/x-www-form-urlencoded',
                   'Accept': 'text/plain'}
        data = urllib.urlencode(args)
        response = requests.post(OAUTH_ACCESS_TOKEN_URL, data=data,
                                 headers=headers)
    except requests.exceptions.HTTPError, e:
        log.error(e)  # TODO better error handling here
        raise e

    session_dict = response.json()
    if u'error' in session_dict:
        if session_dict['error'] == 'invalid_grant':
            log.error('refresh_token_invalid')
            raise InvalidOAuthGrantError('Could not get new token')
        else:
            raise OAuthError(session_dict['error'])

    return session_dict['access_token'], session_dict['expires_in']


# ------------------------------------------------------------------
# Console Support for providing link and reading response from user
# ------------------------------------------------------------------

def _show_authorize_link(email_address=None):
    """ Show authorization link.
    Prints out a message to the console containing a link that the user can
    click on that will bring them to a page that allows them to authorize
    access to their account.
    """
    args = {
        'redirect_uri': REDIRECT_URI,
        'client_id': GOOGLE_OAUTH_CLIENT_ID,
        'response_type': 'code',
        'scope': OAUTH_SCOPE,
        'access_type': 'offline',  # to get a refresh token
    }
    if email_address:
        args['login_hint'] = email_address
    # DEBUG
    args['approval_prompt'] = 'force'

    # Prompt user for authorization + get auth_code
    url = url_concat(OAUTH_AUTHENTICATE_URL, args)
    print ("To authorize Inbox, visit this url and follow the directions:"
           "\n\n{}").format(url)


def _user_info(access_token):
    """ retrieves additional information about the user to store in the db"""
    log.info('fetching_user_info')
    try:
        response = requests.get(USER_INFO_URL +
                                '?access_token=' + access_token)
    except Exception, e:
        log.error('user_info_fetch_failed', error=e)
        return None  # TODO better error handling here

    userinfo_dict = response.json()

    if 'error' in userinfo_dict:
        assert userinfo_dict['error'] == 'invalid_token'
        log.error('user_info_fetch_failed',
                  error=userinfo_dict['error'],
                  error_description=userinfo_dict['error_description'])
        log.error('%s - %s' % (userinfo_dict['error'],
                               userinfo_dict['error_description']))
        return None

    return userinfo_dict


def _get_authenticated_user(authorization_code):
    log.info('Getting oauth authenticated user...')
    args = {
        'client_id': GOOGLE_OAUTH_CLIENT_ID,
        'code': authorization_code,
        'client_secret': GOOGLE_OAUTH_CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'redirect_uri': REDIRECT_URI,
    }

    headers = {'Content-type': 'application/x-www-form-urlencoded',
               'Accept': 'text/plain'}
    data = urllib.urlencode(args)
    resp = requests.post(OAUTH_ACCESS_TOKEN_URL, data=data, headers=headers)

    session_dict = resp.json()

    if u'error' in session_dict:
        raise OAuthError(session_dict['error'])

    access_token = session_dict['access_token']
    validation_dict = validate_token(access_token)
    userinfo_dict = _user_info(access_token)

    z = session_dict.copy()
    z.update(validation_dict)
    z.update(userinfo_dict)

    return z


def oauth_authorize_console(email_address):
    """ Console I/O and checking for a user to authorize their account."""
    _show_authorize_link(email_address)

    while True:
        auth_code = raw_input('Enter authorization code: ').strip()
        try:
            auth_response = _get_authenticated_user(auth_code)
            return auth_response
        except OAuthError:
            print "\nInvalid authorization code, try again...\n"
