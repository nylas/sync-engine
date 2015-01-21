import urllib
import requests
from requests import ConnectionError as RequestsConnectionError
from imapclient import IMAPClient
from socket import gaierror, error as socket_error
from ssl import SSLError
from simplejson import JSONDecodeError
from inbox.auth import AuthHandler
from inbox.basicauth import (ConnectionError, ValidationError,
                             TransientConnectionError, OAuthError,
                             OAuthInvalidGrantError, OAuthValidationError)
from inbox.log import get_logger
log = get_logger()


class OAuthAuthHandler(AuthHandler):
    def connect_account(self, email, pw, imap_endpoint, account_id=None):
        """Provide a connection to a IMAP account.

        Raises
        ------
        socket.error
            If we cannot connect to the IMAP host.
        IMAPClient.error
            If the credentials are invalid.
        """
        host, port = imap_endpoint
        try:
            conn = IMAPClient(host, port=port, use_uid=True, ssl=True)
        except IMAPClient.AbortError as e:
            log.error('account_connect_failed',
                      account_id=account_id,
                      email=email,
                      host=host,
                      port=port,
                      error="[ALERT] Can't connect to host - may be transient")
            raise TransientConnectionError(str(e))
        except(IMAPClient.Error, gaierror, socket_error) as e:
            log.error('account_connect_failed',
                      account_id=account_id,
                      email=email,
                      host=host,
                      port=port,
                      error='[ALERT] (Failure): {0}'.format(str(e)))
            raise ConnectionError(str(e))

        conn.debug = False
        try:
            conn.oauth2_login(email, pw)
        except IMAPClient.AbortError as e:
            log.error('account_verify_failed',
                      account_id=account_id,
                      email=email,
                      host=host,
                      port=port,
                      error="[ALERT] Can't connect to host - may be transient")
            raise TransientConnectionError(str(e))
        except IMAPClient.Error as e:
            log.error('IMAP Login error during connection. '
                      'Account: {}, error: {}'.format(email, e),
                      account_id=account_id)
            if str(e) == '[ALERT] Invalid credentials (Failure)' or \
               str(e) == '[AUTHENTICATIONFAILED] OAuth authentication failed.':
                raise ValidationError(str(e))
            else:
                raise ConnectionError(str(e))
        except SSLError as e:
            log.error('account_verify_failed',
                      account_id=account_id,
                      email=email,
                      host=host,
                      port=port,
                      error='[ALERT] (Failure) SSL Connection error')
            raise ConnectionError(str(e))

        return conn

    def verify_account(self, account):
        """Verifies a IMAP account by logging in."""
        try:
            conn = self.connect_account(account.email_address,
                                        account.access_token,
                                        account.imap_endpoint,
                                        account.id)
            conn.logout()
        except ValidationError:
            # Access token could've expired, refresh and try again.
            conn = self.connect_account(account.email_address,
                                        account.renew_access_token(),
                                        account.imap_endpoint,
                                        account.id)
            conn.logout()

        return True

    def validate_token(self, access_token):
        """Implemented by subclasses."""
        raise NotImplementedError

    def new_token(self, refresh_token, client_id=None, client_secret=None):
        if not refresh_token:
            raise OAuthError('refresh_token required')

        # If these aren't set on the Account object, use the values from
        # config so that the dev version of the sync engine continues to work.
        client_id = client_id or self.OAUTH_CLIENT_ID
        client_secret = client_secret or self.OAUTH_CLIENT_SECRET
        access_token_url = self.OAUTH_ACCESS_TOKEN_URL

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
            response = requests.post(access_token_url, data=data,
                                     headers=headers)
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
        except RequestsConnectionError as e:
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
            raise OAuthValidationError()

        return userinfo_dict
