#!/usr/bin/env python
#
# Copyright 2009 Facebook
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import tornado.auth
import tornado.escape
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
import oauth2

from tornado.options import define, options

define("port", default=8888, help="run on the given port", type=int)


google_permission_emailaddress_url = 'https://www.googleapis.com/auth/userinfo.email'
google_permissions_profile_url = 'https://www.googleapis.com/auth/userinfo.profile'
google_permission_gmail_url = 'https://mail.google.com/'
google_permission_contacts_url = 'https://www.google.com/m8/feeds'
google_permission_calendar_url = 'https://www.googleapis.com/auth/calendar'

class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", MainHandler),
            (r"/auth/login", AuthHandler),
            (r"/auth/logout", LogoutHandler),
        ]
        settings = dict(
            cookie_secret="32oETzKXQAGaYdkL5gEmGeJJFuYh7EQnp2XdTP1o/Vo=",
            login_url="/auth/login",
            redirect_uri="http://localhost:8888/auth/login",

            google_consumer_key="786647191490.apps.googleusercontent.com",  # client ID
            google_consumer_secret="0MnVfEYfFebShe9576RR8MCK",  # client secret

            google_permissions = " ".join([google_permission_emailaddress_url,
                                           google_permissions_profile_url,
                                           google_permission_gmail_url, 
                                           google_permission_contacts_url,
                                           google_permission_calendar_url]),

            google_permissions2="https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/userinfo.email"
        )
        tornado.web.Application.__init__(self, handlers, **settings)


class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        user_json = self.get_secure_cookie("user")
        if not user_json: return None
        return tornado.escape.json_decode(user_json)


class MainHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        name = tornado.escape.xhtml_escape(self.current_user["name"])
        self.write("Hello, " + name)
        self.write("<br><br><a href=\"/auth/logout\">Log out</a>")


class AuthHandler(BaseHandler, oauth2.GoogleOAuth2Mixin):
    @tornado.web.asynchronous
    def get(self):
        if self.get_argument("code", None):
            authorization_code = self.get_argument("code", None)
            self.get_authenticated_user(authorization_code, self.async_callback(self._on_auth))
            return
        self.authorize_redirect(self.settings['google_permissions'])
    
    def _on_auth(self, response):
        print 'RESPONSE:', response
        # print response.body
        # print response.request.headers
        # if response.error:
        #     raise tornado.web.HTTPError(500, "Google auth failed")

        user = response.read()
        print user
        # self.set_secure_cookie("user", tornado.escape.json_encode(user))
        self.set_secure_cookie("user", user)
        self.redirect("/")

class LogoutHandler(BaseHandler):
    def get(self):
        self.clear_cookie("user")
        self.redirect("/")

def main():
    tornado.options.parse_command_line()
    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()