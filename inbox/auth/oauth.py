import urllib
import requests

from inbox.util.url import url_concat
from inbox.log import get_logger
log = get_logger()
from inbox.config import config, ConfigError
from inbox.basicauth import AuthError

# Google OAuth app credentials
GOOGLE_OAUTH_CLIENT_ID = config.get('GOOGLE_OAUTH_CLIENT_ID', None)
GOOGLE_OAUTH_CLIENT_SECRET = config.get('GOOGLE_OAUTH_CLIENT_SECRET', None)
REDIRECT_URI = config.get('GOOGLE_OAUTH_REDIRECT_URI', None)
if not (GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET and
        REDIRECT_URI):
    raise ConfigError('Missing Google OAuth Credentials.')

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


def authorize_redirect_url(email_address=None):
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
    print '''
To authorize Inbox, visit this url and follow the directions:

{0}
'''.format(url)

    auth_code = raw_input('Enter authorization code: ').strip()
    return auth_code


def get_authenticated_user(authorization_code):
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
    response = requests.post(OAUTH_ACCESS_TOKEN_URL, data=data,
                             headers=headers)

    session_dict = response.json()

    if u'error' in session_dict:
        raise OAuthError(session_dict['error'])

    access_token = session_dict['access_token']
    validation_dict = validate_token(access_token)
    userinfo_dict = user_info(access_token)

    z = session_dict.copy()
    z.update(validation_dict)
    z.update(userinfo_dict)

    return z

    # TODO : get this data somewhere other than the auth module


def get_new_token(refresh_token):
    assert refresh_token is not None, 'refresh_token required'

    log.info('Getting new oauth token...')
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
            log.error('Refresh token is invalid.')
            raise InvalidOAuthGrantError('Could not get new token')
        else:
            raise OAuthError(session_dict['error'])

    access_token = session_dict['access_token']

    # Validate token
    validation_dict = validate_token(access_token)

    z = session_dict.copy()
    z.update(validation_dict)
    return z


def validate_token(access_token):
    log.info('Validating oauth token...')
    try:
        response = requests.get(OAUTH_TOKEN_VALIDATION_URL +
                                '?access_token=' + access_token)
    except Exception, e:
        log.error(e)
        return None  # TODO better error handling here

    validation_dict = response.json()

    if 'error' in validation_dict:
        assert validation_dict['error'] == 'invalid_token'
        log.error('{0} - {1}'.format(validation_dict['error'],
                                     validation_dict['error_description']))
        return None

    return validation_dict


def user_info(access_token):
    log.info('Fetching user info...')

    try:
        response = requests.get(USER_INFO_URL +
                                '?access_token=' + access_token)
    except Exception, e:
        log.error(e)
        return None  # TODO better error handling here

    userinfo_dict = response.json()

    if 'error' in userinfo_dict:
        assert userinfo_dict['error'] == 'invalid_token'
        log.error('%s - %s' % (userinfo_dict['error'],
                               userinfo_dict['error_description']))
        return None

    return userinfo_dict


def oauth_authorize(email_address):
    auth_code = authorize_redirect_url(email_address)

    try:
        auth_response = get_authenticated_user(auth_code)
    except OAuthError:
        reentered_code = raw_input('\nInvalid authorization code, try again: '
                                   ).strip()
        auth_response = get_authenticated_user(reentered_code)

    return auth_response
