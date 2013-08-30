from util import url_concat
import logging as log
import urllib
from os import environ
import requests

GOOGLE_CONSUMER_KEY = environ.get("GOOGLE_CONSUMER_KEY", None)
GOOGLE_CONSUMER_SECRET = environ.get("GOOGLE_CONSUMER_SECRET", None)
assert GOOGLE_CONSUMER_KEY, "Missing Google OAuth Consumer Key"
assert GOOGLE_CONSUMER_SECRET, "Missing Google OAuth Consumer Secret"

OAUTH_AUTHENTICATE_URL = "https://accounts.google.com/o/oauth2/auth"
OAUTH_ACCESS_TOKEN_URL = "https://accounts.google.com/o/oauth2/token"
OAUTH_TOKEN_VALIDATION_URL = "https://www.googleapis.com/oauth2/v1/tokeninfo"
USER_INFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo"

OAUTH_SCOPE = " ".join([
    'https://www.googleapis.com/auth/userinfo.email',  # email address
    'https://www.googleapis.com/auth/userinfo.profile',  # G+ profile
    'https://mail.google.com/',  # email
    'https://www.google.com/m8/feeds',  # contacts
    'https://www.googleapis.com/auth/calendar'  # calendar
    ])


def authorize_redirect_url(redirect_uri, email_address=None):
    """ Create the URL to redirect for Google oauth2 """
    # TODO https://developers.google.com/accounts/docs/OAuth2WebServer
    args = {
      "redirect_uri": redirect_uri,
      "client_id": GOOGLE_CONSUMER_KEY,
      "response_type": "code",
      "scope": OAUTH_SCOPE,
      "access_type" : "offline",  # to get a refresh token
    }
    if email_address:
        args['login_hint'] = email_address
    # DEBUG
    args["approval_prompt"] = "force"

    return url_concat(OAUTH_AUTHENTICATE_URL, args)



def get_authenticated_user(authorization_code, redirect_uri):
    log.info("Getting oauth authentiated user...")
    args = {
        "client_id": GOOGLE_CONSUMER_KEY,
        "code": authorization_code,
        "client_secret": GOOGLE_CONSUMER_SECRET,
        "grant_type": "authorization_code",
        "redirect_uri" : redirect_uri
    }

    try:
        headers = {'Content-type': 'application/x-www-form-urlencoded', 'Accept': 'text/plain'}
        data = urllib.urlencode(args)
        response = requests.post(OAUTH_ACCESS_TOKEN_URL, data=data, headers=headers )
    except Exception, e:
        log.error(e)
        return None  # TODO better error handling here

    session_dict = response.json()

    if u'error' in session_dict:
        log.error("Error when getting authenticated user: %s" % session_dict['error'])
        return None


    access_token = session_dict['access_token']
    validation_dict = validate_token(access_token)

    z = session_dict.copy()
    z.update(validation_dict)
    return z

    # TODO : get this data somwhere other than the auth module


def get_new_token(refresh_token):
    if not refresh_token: return None
    log.info("Getting new oauth token...")
    args = {
        "refresh_token": refresh_token,
        "client_id": GOOGLE_CONSUMER_KEY,
        "client_secret": GOOGLE_CONSUMER_SECRET,
        'grant_type' : 'refresh_token'
    }

    try:
        headers = {'Content-type': 'application/x-www-form-urlencoded', 'Accept': 'text/plain'}
        data = urllib.urlencode(args)
        response = requests.post(OAUTH_ACCESS_TOKEN_URL, data=data, headers=headers )
    except Exception, e:
        log.error(e)
        return None  # TODO better error handling here

    session_dict = response.json()
    if u'error' in session_dict:
        log.error("Error when getting authenticated user: %s" % session_dict['error'])
        return None


    access_token = session_dict['access_token']

    # Validate token
    validation_dict = validate_token(access_token)

    z = session_dict.copy()
    z.update(validation_dict)
    return z


def validate_token(access_token):
    log.info("Validating oauth token...")
    try:
        response = requests.get(OAUTH_TOKEN_VALIDATION_URL + "?access_token=" + access_token )
    except Exception, e:
        log.error(e)
        return None  # TODO better error handling here

    validation_dict = response.json()

    if 'error' in validation_dict:
        assert validation_dict['error'] == 'invalid_token'
        log.error("%s - %s" % (validation_dict['error'], validation_dict['error_description']))
        return None

    return validation_dict
