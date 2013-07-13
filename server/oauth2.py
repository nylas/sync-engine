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


class GoogleOAuth2Mixin(tornado.auth.OAuth2Mixin):

    access_token = ""
    _OAUTH_AUTHENTICATE_URL = "https://accounts.google.com/o/oauth2/auth"
    _OAUTH_ACCESS_TOKEN_URL = "https://accounts.google.com/o/oauth2/token"
    _OAUTH_TOKEN_VALIDATION_URL = "https://www.googleapis.com/oauth2/v1/tokeninfo"
    _USER_INFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo"

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
        self.redirect(url_concat(self._OAUTH_AUTHENTICATE_URL, args))

    @tornado.gen.engine
    def get_authenticated_user(self, authorization_code, callback):

        args = {
            "redirect_uri": self.settings['redirect_uri'],
            "client_id": self.settings['google_consumer_key'],
            "code": authorization_code,
            "client_secret": self.settings['google_consumer_secret'],
            "grant_type": "authorization_code"
        }
        
        request = httpclient.HTTPRequest(self._OAUTH_ACCESS_TOKEN_URL, method="POST", body=urllib.urlencode(args))
        
        response = yield tornado.gen.Task(self.httpclient_instance.fetch, request)

        print '_on_access_token', response

        if response.error:
            logging.warning('Google auth error: %s' % str(response))
            callback(None)
            return

        session = escape.json_decode(response.body)

        GoogleOAuth2Mixin.access_token = session['access_token']

        self.validate_token(session, callback)
    
    def validate_token(self, session, callback):

        print 'validate_token', session

        self.httpclient_instance.fetch(
            self._OAUTH_TOKEN_VALIDATION_URL+"?access_token="+session['access_token'],
            self.async_callback(self.get_user_info, session, callback)
        )


    def get_user_info(self, session, callback, response):

        GoogleOAuth2Mixin.access_token = session['access_token']

        print 'Access token', GoogleOAuth2Mixin.access_token

        additional_headers = {
            "Authorization": "Bearer "+GoogleOAuth2Mixin.access_token
        }

        h = httputil.HTTPHeaders()
        h.parse_line("Authorization: Bearer "+GoogleOAuth2Mixin.access_token)
        conn = httplib.HTTPSConnection("www.googleapis.com")
        conn.request("GET", "/oauth2/v1/userinfo?access_token="+GoogleOAuth2Mixin.access_token, "", additional_headers)

        # https://www.googleapis.com/userinfo/email?alt=json

        response = conn.getresponse()


        # user_info = escape.json_decode(response.body)
        # print 'user_info: ', user_info
        callback(response)


        # r =  response.read()

        # session['name'] = r['name']
        # print 'printed response', r

        #h.pop("Accept-Encoding")
        '''request = httpclient.HTTPRequest(self._USER_INFO_URL+"?access_token="+GoogleOAuth2Mixin.access_token, method="GET", headers=h)
        self.httpclient_instance.fetch(
            request,
            self.async_callback(callback)
        )'''

        # No error I guess? 
        # callback(session)
        
    def _on_response(self):
        if response.error:
            logging.warning('Google get user info error: %s' % str(response))
            callback(None)
            return

        user_info = escape.json_decode(response.body)
        print 'user_info: ', user_info
        callback(user_info)
