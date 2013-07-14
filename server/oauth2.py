import tornado.auth
from tornado import httpclient
from tornado import httputil
from tornado.httputil import url_concat
from tornado import escape
import tornado.gen
import logging
import urllib
import urllib2
import urlparse
import httplib
import urllib
import xoauth


scope = " ".join([
    'https://www.googleapis.com/auth/userinfo.email',  # email address
    'https://www.googleapis.com/auth/userinfo.profile',  # G+ profile
    'https://mail.google.com/',  # email
    'https://www.google.com/m8/feeds',  # contacts
    'https://www.googleapis.com/auth/calendar'  #calendar
    ])


OAUTH_AUTHENTICATE_URL = "https://accounts.google.com/o/oauth2/auth"
OAUTH_ACCESS_TOKEN_URL = "https://accounts.google.com/o/oauth2/token"
OAUTH_TOKEN_VALIDATION_URL = "https://www.googleapis.com/oauth2/v1/tokeninfo"
USER_INFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo"


class GoogleOAuth2Mixin(tornado.auth.OAuth2Mixin):

    access_token = ""

    @property
    def httpclient_instance(self):
        return httpclient.AsyncHTTPClient()


    def authorize_redirect(self, **kwargs):
        args = {
          "redirect_uri": self.settings['redirect_uri'],
          "client_id": self.settings['google_consumer_key'],
          "response_type": "code",
          "scope": scope,

          # 'state' should include the value of the anti-forgery unique session token, 
          # as well as any other information needed to recover the context when the 
          # user returns to your application (e.g., the starting URL).

          # login_hint should be the email address of the user if you know it. 
          # If not provided and the user is currently logged in, the consent page 
          # will also request permission for your app to see the user's email. 
          # Providing the login_hint simplifies the consent screen and can also streamline 
          # the login experience for users that are using Google's multilogin feature.

          "login_hint" : "mgrinich@gmail.com"

        }
        if kwargs: args.update(kwargs)
        self.redirect(url_concat(OAUTH_AUTHENTICATE_URL, args))
        

    @tornado.gen.engine
    def get_authenticated_user(self, authorization_code, callback):

        args = {
            "redirect_uri": self.settings['redirect_uri'],
            "client_id": self.settings['google_consumer_key'],
            "code": authorization_code,
            "client_secret": self.settings['google_consumer_secret'],
            "grant_type": "authorization_code"
        }
        
        request = httpclient.HTTPRequest(OAUTH_ACCESS_TOKEN_URL, method="POST", body=urllib.urlencode(args))
        response = yield tornado.gen.Task(self.httpclient_instance.fetch, request)


        if response.error:
            error_dict = escape.json_decode(response.body)
            logging.error('[%s] %s' % (error_dict['error'], error_dict['error_description']))
            callback(None)
            return

        session_dict = escape.json_decode(response.body)
        access_token = session_dict['access_token']

        # Validate token
        request = httpclient.HTTPRequest(OAUTH_TOKEN_VALIDATION_URL + "?access_token=" + access_token)
        response = yield tornado.gen.Task(self.httpclient_instance.fetch, request)


        if response.error:
            error_dict = escape.json_decode(response.body)
            logging.error('[%s] %s' % (error_dict['error'], error_dict['error_description']))
            callback(None)
            return

        validation_dict = escape.json_decode(response.body)
        email_address = validation_dict["email"]


        callback( dict(email_address=email_address, access_token=access_token) )


        # TODO : get this data somwhere other than the auth module


        # Get user info. Stuff like fullname, birthdate, profile picture, etc.
        # request = httpclient.HTTPRequest(USER_INFO_URL+"?access_token="+GoogleOAuth2Mixin.access_token, 
        #                                  headers= { "Authorization": "Bearer "+ access_token } )
        # response = yield tornado.gen.Task(self.httpclient_instance.fetch, request)
        # userinfo_dict = escape.json_decode(response.body)
        # print userinfo_dict


        