from tornado import httpclient
from tornado import httputil
from tornado.httputil import url_concat
from tornado import escape
import logging as log
import urllib

from secrets import GOOGLE_CONSUMER_KEY, GOOGLE_CONSUMER_SECRET

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


async_client = httpclient.HTTPClient()  # Todo make async?


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

    args = {
        "client_id": GOOGLE_CONSUMER_KEY,
        "code": authorization_code,
        "client_secret": GOOGLE_CONSUMER_SECRET,
        "grant_type": "authorization_code",
        "redirect_uri" : redirect_uri
    }

    request = httpclient.HTTPRequest(OAUTH_ACCESS_TOKEN_URL, method="POST", body=urllib.urlencode(args))
    response = async_client.fetch( request)

    if response.error:
        error_dict = escape.json_decode(response.body)
        log.error(error_dict)
        return None

    session_dict = escape.json_decode(response.body)
    access_token = session_dict['access_token']

    validation_dict = validate_token(access_token)

    z = session_dict.copy()
    z.update(validation_dict)
    return z

    # TODO : get this data somwhere other than the auth module


def get_new_token(refresh_token):
    if not refresh_token: return None

    args = {
        "refresh_token": refresh_token,
        "client_id": GOOGLE_CONSUMER_KEY,
        "client_secret": GOOGLE_CONSUMER_SECRET,
        'grant_type' : 'refresh_token'
    }


    request = httpclient.HTTPRequest(OAUTH_ACCESS_TOKEN_URL, method="POST", body=urllib.urlencode(args))

    response = async_client.fetch(request)

    if response.error:
        error_dict = escape.json_decode(response.body)
        log.error(error_dict)
        return None

    session_dict = escape.json_decode(response.body)
    access_token = session_dict['access_token']

    # Validate token
    validation_dict = validate_token(access_token)

    z = session_dict.copy()
    z.update(validation_dict)
    return z


def validate_token(access_token):
    # Validate token
    request = httpclient.HTTPRequest(OAUTH_TOKEN_VALIDATION_URL + "?access_token=" + access_token)

    try:
        response = async_client.fetch(request)
    except httpclient.HTTPError, e:
        response = e.response
        pass  # handle below
    except Exception, e:
        log.error(e)
        raise e

    validation_dict = escape.json_decode(response.body)

    if 'error' in validation_dict:
        assert validation_dict['error'] == 'invalid_token'
        log.error("%s - %s" % (validation_dict['error'], validation_dict['error_description']))
        return None


    validation_dict = escape.json_decode(response.body)
    return validation_dict



def get_user_info(access_token, redirect_uri, callback):
    """ Get user info. Stuff like fullname, birthdate, profile picture, etc. """

    request = httpclient.HTTPRequest(OAUTH_ACCESS_TOKEN_URL, method="POST", body=urllib.urlencode(args))
    response = async_client.fetch(request)

    if response.error:
        error_dict = escape.json_decode(response.body)
        log.error(error_dict)
        return None

    return userinfo_dict

