import sys
import urllib
import requests
from simplejson import JSONDecodeError
from requests import ConnectionError as RequestsConnectionError

from inbox.util.url import url_concat
from inbox.log import get_logger
log = get_logger()
from inbox.basicauth import ValidationError, ConnectionError


class OAuthError(ValidationError):
    pass


class OAuthValidationError(OAuthError):
    pass


class OAuthInvalidGrantError(OAuthError):
    pass


def validate_token(provider_module, access_token):
    """ Helper function which will validate an access token.

    Returns
    -------
    validation_dict if connecting and validation succeeds

    Raises
    ------
    ConnectionError
        When unable to connect to oauth host
    OAuthErrro
        When authorization fails
    """

    try:
        validation_url = provider_module.OAUTH_TOKEN_VALIDATION_URL
    except AttributeError:
        return _user_info(provider_module, access_token)

    try:
        response = requests.get(validation_url +
                                '?access_token=' + access_token)
    except RequestsConnectionError as e:
        raise ConnectionError(e)

    validation_dict = response.json()

    if 'error' in validation_dict:
        raise OAuthValidationError(validation_dict['error'])

    return validation_dict


def new_token(provider_module, refresh_token, client_id=None,
              client_secret=None):
    """ Helper function which gets a new access token from a refresh token."""
    assert refresh_token is not None, 'refresh_token required'

    # If these aren't set on the Account object, use the values from
    # config so that the dev version of the sync engine continues to work.
    try:
        client_id = client_id or provider_module.OAUTH_CLIENT_ID
        client_secret = client_secret or provider_module.OAUTH_CLIENT_SECRET
        access_token_url = provider_module.OAUTH_ACCESS_TOKEN_URL
    except AttributeError:
        log.error("Provider module must define OAUTH_CLIENT_ID,"
                  "OAUTH_CLIENT_SECRET and OAUTH_ACCESS_TOKEN_URL")
        raise

    args = {
        'refresh_token': refresh_token,
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'refresh_token'
    }

    try:
        headers = {'Content-type': 'application/x-www-form-urlencoded',
                   'Accept': 'text/plain'}
        data = urllib.urlencode(args)
        response = requests.post(access_token_url, data=data, headers=headers)
    except (requests.exceptions.HTTPError, RequestsConnectionError), e:
        log.error(e)
        raise ConnectionError()

    try:
        session_dict = response.json()
    except JSONDecodeError:
        raise ConnectionError("Invalid json: " + response.text)

    if u'error' in session_dict:
        if session_dict['error'] == 'invalid_grant':
            raise OAuthInvalidGrantError('Invalid refresh token.')
        else:
            raise OAuthError(session_dict['error'])

    return session_dict['access_token'], session_dict['expires_in']


# ------------------------------------------------------------------
# Console Support for providing link and reading response from user
# ------------------------------------------------------------------

def authorize_link(provider_module, email_address=None):
    """ Show authorization link.
    Prints out a message to the console containing a link that the user can
    click on that will bring them to a page that allows them to authorize
    access to their account.
    """

    try:
        redirect_uri = provider_module.OAUTH_REDIRECT_URI
        client_id = provider_module.OAUTH_CLIENT_ID
        scope = provider_module.OAUTH_SCOPE
        authenticate_url = provider_module.OAUTH_AUTHENTICATE_URL
    except AttributeError:
        log.error("Provider module must define OAUTH_REDIRECT_URI, "
                  "OAUTH_CLIENT_ID, OAUTH_SCOPE and OAUTH_AUTHENTICATE_URL")
        raise

    args = {
        'redirect_uri': redirect_uri,
        'client_id': client_id,
        'response_type': 'code',
        'scope': scope,
        'access_type': 'offline',  # to get a refresh token
    }

    # TODO: Is there some way to make this generic? Outlook doesn't
    # accept a login_hint. -cg3
    if provider_module.PROVIDER == 'gmail' and email_address:
        args['login_hint'] = email_address

    # Prompt user for authorization + get auth_code
    url = url_concat(authenticate_url, args)
    return url


def _user_info(provider_module, access_token):
    """ retrieves additional information about the user to store in the db"""
    log.info('fetching_user_info')
    try:
        user_info_url = provider_module.OAUTH_USER_INFO_URL
        args = {'access_token': access_token}
        response = requests.get(user_info_url + "?" +
                                urllib.urlencode(args))
    except RequestsConnectionError as e:
        log.error('user_info_fetch_failed', error=e)
        raise ConnectionError()
    except AttributeError:
        log.error('Provider module must have OAUTH_USER_INFO_URL.')
        raise

    userinfo_dict = response.json()

    if 'error' in userinfo_dict:
        assert userinfo_dict['error'] == 'invalid_token'
        log.error('user_info_fetch_failed',
                  error=userinfo_dict['error'],
                  error_description=userinfo_dict['error_description'])
        log.error('%s - %s' % (userinfo_dict['error'],
                               userinfo_dict['error_description']))
        raise OAuthValidationError()

    return userinfo_dict


def _get_authenticated_user(provider_module, authorization_code):
    log.info('Getting oauth authenticated user...')

    try:
        client_id = provider_module.OAUTH_CLIENT_ID
        client_secret = provider_module.OAUTH_CLIENT_SECRET
        access_token_url = provider_module.OAUTH_ACCESS_TOKEN_URL
        redirect_uri = provider_module.OAUTH_REDIRECT_URI
    except AttributeError:
        log.error("Provider module must define OAUTH_CLIENT_ID,"
                  "OAUTH_CLIENT_SECRET, OAUTH_ACCESS_TOKEN_URL"
                  " and OAUTH_REDIRECT_URI")
        raise

    args = {
        'client_id': client_id,
        'code': authorization_code,
        'client_secret': client_secret,
        'grant_type': 'authorization_code',
        'redirect_uri': redirect_uri,
    }

    headers = {'Content-type': 'application/x-www-form-urlencoded',
               'Accept': 'text/plain'}
    data = urllib.urlencode(args)
    resp = requests.post(access_token_url, data=data, headers=headers)

    session_dict = resp.json()

    if u'error' in session_dict:
        raise OAuthError(session_dict['error'])

    access_token = session_dict['access_token']
    validation_dict = validate_token(provider_module, access_token)
    userinfo_dict = _user_info(provider_module, access_token)

    z = session_dict.copy()
    z.update(validation_dict)
    z.update(userinfo_dict)

    return z


def oauth_authorize_console(provider_module, email_address, token, exit):
    """ Console I/O and checking for a user to authorize their account."""
    if not token:
        url = authorize_link(provider_module, email_address)
        print ("\n\n{}").format(url)
        if exit:
            sys.exit(0)
    else:
        auth_code = token

    while True:
        if not token:
            auth_code = raw_input('Enter authorization code: ').strip()
        try:
            auth_response = _get_authenticated_user(provider_module, auth_code)
            return auth_response
        except OAuthError:
            print "\nInvalid authorization code, try again...\n"
            auth_code = None
