import urllib
import socket
from simplejson import JSONDecodeError

import requests
from imapclient import IMAPClient

from nylas.logging import get_logger
log = get_logger()
from inbox.auth.base import AuthHandler
from inbox.auth.generic import create_imap_connection
from inbox.basicauth import ConnectionError, OAuthError
from inbox.models.backends.oauth import token_manager


class OAuthAuthHandler(AuthHandler):

    def connect_account(self, account, use_timeout=True):
        """
        Returns an authenticated IMAP connection for the given account.

        Raises
        ------
        ValidationError
            If fetching an access token failed because the refresh token we
            have is invalid (i.e., if the user has revoked access).
        ConnectionError
            If another error occurred when fetching an access token.
        imapclient.IMAPClient.Error, socket.error
            If errors occurred establishing the connection or logging in.

        """
        conn = self._get_IMAP_connection(account, use_timeout)
        self._authenticate_IMAP_connection(account, conn)
        return conn

    def _get_IMAP_connection(self, account, use_timeout=True):
        host, port = account.imap_endpoint
        try:
            conn = create_imap_connection(host, port, ssl_required=True,
                                          use_timeout=use_timeout)
        except (IMAPClient.Error, socket.error) as exc:
            log.error('Error instantiating IMAP connection',
                      account_id=account.id,
                      imap_host=host,
                      imap_port=port,
                      error=exc)
            raise
        return conn

    def _authenticate_IMAP_connection(self, account, conn):
        host, port = account.imap_endpoint
        try:
            # Raises ValidationError if the refresh token we have is invalid.
            token = token_manager.get_token(account)
            conn.oauth2_login(account.email_address, token)
        except IMAPClient.Error as exc:
            log.error('Error during IMAP XOAUTH2 login',
                      account_id=account.id,
                      host=host,
                      port=port,
                      error=exc)
            raise

    def verify_account(self, account):
        """Verifies an IMAP account by logging in."""
        conn = self.connect_account(account)
        conn.logout()
        return True

    def new_token(self, refresh_token, client_id=None, client_secret=None):
        if not refresh_token:
            raise OAuthError('refresh_token required')

        # If these aren't set on the Account object, use the values from
        # config so that the dev version of the sync engine continues to work.
        client_id = client_id or self.OAUTH_CLIENT_ID
        client_secret = client_secret or self.OAUTH_CLIENT_SECRET
        access_token_url = self.OAUTH_ACCESS_TOKEN_URL

        data = urllib.urlencode({
            'refresh_token': refresh_token,
            'client_id': client_id,
            'client_secret': client_secret,
            'grant_type': 'refresh_token'
        })
        headers = {'Content-type': 'application/x-www-form-urlencoded',
                   'Accept': 'text/plain'}
        try:
            response = requests.post(access_token_url, data=data,
                                     headers=headers)
        except requests.exceptions.ConnectionError as e:
            log.error('Network error renewing access token', error=e)
            raise ConnectionError()

        try:
            session_dict = response.json()
        except JSONDecodeError:
            log.error('Invalid JSON renewing on renewing token',
                      response=response.text)
            raise ConnectionError('Invalid JSON response on renewing token')

        if 'error' in session_dict:
            if session_dict['error'] == 'invalid_grant':
                # This is raised if the user has revoked access to the
                # application (or if the refresh token is otherwise invalid).
                raise OAuthError('invalid_grant')
            elif session_dict['error'] == 'deleted_client':
                # If the developer has outright deleted their Google OAuth app
                # ID. We treat this too as a case of 'invalid credentials'.
                raise OAuthError('deleted_client')
            else:
                # You can also get e.g. {"error": "internal_failure"}
                log.error('Error renewing access token',
                          session_dict=session_dict)
                raise ConnectionError('Server error renewing access token')

        return session_dict['access_token'], session_dict['expires_in']

    def _get_authenticated_user(self, authorization_code):
        args = {
            'client_id': self.OAUTH_CLIENT_ID,
            'client_secret': self.OAUTH_CLIENT_SECRET,
            'redirect_uri': self.OAUTH_REDIRECT_URI,
            'code': authorization_code,
            'grant_type': 'authorization_code'
        }

        headers = {'Content-type': 'application/x-www-form-urlencoded',
                   'Accept': 'text/plain'}
        data = urllib.urlencode(args)
        resp = requests.post(self.OAUTH_ACCESS_TOKEN_URL, data=data,
                             headers=headers)

        session_dict = resp.json()

        if u'error' in session_dict:
            raise OAuthError(session_dict['error'])

        access_token = session_dict['access_token']
        validation_dict = self.validate_token(access_token)
        userinfo_dict = self._get_user_info(access_token)

        z = session_dict.copy()
        z.update(validation_dict)
        z.update(userinfo_dict)

        return z

    def _get_user_info(self, access_token):
        try:
            response = requests.get(self.OAUTH_USER_INFO_URL,
                                    params={'access_token': access_token})
        except requests.exceptions.ConnectionError as e:
            log.error('user_info_fetch_failed', error=e)
            raise ConnectionError()

        userinfo_dict = response.json()

        if 'error' in userinfo_dict:
            assert userinfo_dict['error'] == 'invalid_token'
            log.error('user_info_fetch_failed',
                      error=userinfo_dict['error'],
                      error_description=userinfo_dict['error_description'])
            log.error('%s - %s' % (userinfo_dict['error'],
                                   userinfo_dict['error_description']))
            raise OAuthError()

        return userinfo_dict


class OAuthRequestsWrapper(requests.auth.AuthBase):
    """Helper class for setting the Authorization header on HTTP requests."""

    def __init__(self, token):
        self.token = token

    def __call__(self, r):
        r.headers['Authorization'] = 'Bearer {}'.format(self.token)
        return r
