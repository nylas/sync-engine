from tornado import httpclient
from tornado import httputil
from tornado.httputil import url_concat
from tornado import escape
import tornado.gen
import logging
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


async_client = httpclient.AsyncHTTPClient()


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


@tornado.gen.engine
def get_authenticated_user(authorization_code, redirect_uri, callback):

    args = {
        "client_id": GOOGLE_CONSUMER_KEY,
        "code": authorization_code,
        "client_secret": GOOGLE_CONSUMER_SECRET,
        "grant_type": "authorization_code",
        "redirect_uri" : redirect_uri
    }

    request = httpclient.HTTPRequest(OAUTH_ACCESS_TOKEN_URL, method="POST", body=urllib.urlencode(args))
    response = yield tornado.gen.Task(async_client.fetch, request)

    if response.error:
        error_dict = escape.json_decode(response.body)
        logging.error(error_dict)
        callback(None)
        return

    session_dict = escape.json_decode(response.body)
    access_token = session_dict['access_token']

    validation_dict = yield tornado.gen.Task(validate_token, access_token)

    z = session_dict.copy()
    z.update(validation_dict)
    callback(z)

    # TODO : get this data somwhere other than the auth module


@tornado.gen.engine
def get_new_token(refresh_token, callback):

    if not refresh_token:
        callback(None)
        return

    args = {
        "refresh_token": refresh_token,
        "client_id": GOOGLE_CONSUMER_KEY,
        "client_secret": GOOGLE_CONSUMER_SECRET,
        'grant_type' : 'refresh_token'
    }
    

    request = httpclient.HTTPRequest(OAUTH_ACCESS_TOKEN_URL, method="POST", body=urllib.urlencode(args))

    response = yield tornado.gen.Task(async_client.fetch, request)

    if response.error:
        error_dict = escape.json_decode(response.body)
        logging.error(error_dict)
        callback(None)
        return

    session_dict = escape.json_decode(response.body)
    access_token = session_dict['access_token']

    # Validate token
    validation_dict = yield tornado.gen.Task(validate_token, access_token)

    z = session_dict.copy()
    z.update(validation_dict)
    callback(z)



@tornado.gen.engine
def validate_token(access_token, callback=None):

    # Validate token
    request = httpclient.HTTPRequest(OAUTH_TOKEN_VALIDATION_URL + "?access_token=" + access_token)
    response = yield tornado.gen.Task(async_client.fetch, request)

    if response.error:
        error_dict = escape.json_decode(response.body)
        logging.error('[%s] %s' % (error_dict['error'], error_dict['error_description']))
        callback(None)
        return

    validation_dict = escape.json_decode(response.body)
    callback(validation_dict)
    return



@tornado.gen.engine
def get_user_info(access_token, redirect_uri, callback):
    """ Get user info. Stuff like fullname, birthdate, profile picture, etc. """

    request = httpclient.HTTPRequest(OAUTH_ACCESS_TOKEN_URL, method="POST", body=urllib.urlencode(args))
    response = yield tornado.gen.Task(async_client.fetch, request)
    
    if response.error:
        error_dict = escape.json_decode(response.body)
        logging.error(error_dict)
        callback(None)
        return

    callback(userinfo_dict)

        