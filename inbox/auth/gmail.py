import requests
from sqlalchemy.orm.exc import NoResultFound

from imapclient import IMAPClient
from inbox.models import Namespace
from inbox.models.backends.gmail import GmailAccount
from inbox.models.backends.gmail import GmailAuthCredentials
from inbox.models.backends.gmail import g_token_manager
from inbox.config import config
from inbox.auth.oauth import OAuthAuthHandler
from inbox.basicauth import OAuthError, UserRecoverableConfigError
from inbox.util.url import url_concat
from inbox.providers import provider_info
from inbox.crispin import GmailCrispinClient, GmailSettingError

from inbox.log import get_logger
log = get_logger()

PROVIDER = 'gmail'
AUTH_HANDLER_CLS = 'GmailAuthHandler'

# Google OAuth app credentials
OAUTH_CLIENT_ID = config.get_required('GOOGLE_OAUTH_CLIENT_ID')
OAUTH_CLIENT_SECRET = config.get_required('GOOGLE_OAUTH_CLIENT_SECRET')
OAUTH_REDIRECT_URI = config.get_required('GOOGLE_OAUTH_REDIRECT_URI')

OAUTH_AUTHENTICATE_URL = 'https://accounts.google.com/o/oauth2/auth'
OAUTH_ACCESS_TOKEN_URL = 'https://accounts.google.com/o/oauth2/token'
OAUTH_TOKEN_VALIDATION_URL = 'https://www.googleapis.com/oauth2/v1/tokeninfo'
OAUTH_USER_INFO_URL = 'https://www.googleapis.com/oauth2/v1/userinfo'

# NOTE: urls for email address and G+ profile are deprecated
OAUTH_SCOPE = ' '.join([
    'https://www.googleapis.com/auth/userinfo.email',  # email address
    'https://www.googleapis.com/auth/userinfo.profile',  # G+ profile
    'https://mail.google.com/',  # email
    'https://www.google.com/m8/feeds',  # contacts
    'https://www.googleapis.com/auth/calendar'  # calendar
])


class GmailAuthHandler(OAuthAuthHandler):
    OAUTH_CLIENT_ID = OAUTH_CLIENT_ID
    OAUTH_CLIENT_SECRET = OAUTH_CLIENT_SECRET
    OAUTH_REDIRECT_URI = OAUTH_REDIRECT_URI
    OAUTH_AUTHENTICATE_URL = OAUTH_AUTHENTICATE_URL
    OAUTH_ACCESS_TOKEN_URL = OAUTH_ACCESS_TOKEN_URL
    OAUTH_TOKEN_VALIDATION_URL = OAUTH_TOKEN_VALIDATION_URL
    OAUTH_USER_INFO_URL = OAUTH_USER_INFO_URL
    OAUTH_SCOPE = OAUTH_SCOPE

    def _authenticate_IMAP_connection(self, account, conn):
        """
        Overrides the same method in OAuthAuthHandler so that
        we can choose a token w/ the appropriate scope.
        """
        host, port = account.imap_endpoint
        try:
            token = g_token_manager.get_token_for_email(account)
            conn.oauth2_login(account.email_address, token)
        except IMAPClient.Error as exc:
            log.error('Error during IMAP XOAUTH2 login',
                      account_id=account.id,
                      email=account.email_address,
                      host=host,
                      port=port,
                      error=exc)
            raise

    def create_account(self, db_session, email_address, response):
        email_address = response.get('email')
        # See if the account exists in db, otherwise create it
        try:
            account = db_session.query(GmailAccount) \
                .filter_by(email_address=email_address).one()
        except NoResultFound:
            namespace = Namespace()
            account = GmailAccount(namespace=namespace)

        # We only get refresh tokens on initial login (or failed credentials)
        # otherwise, we don't force the login screen and therefore don't get a
        # refresh token back from google.
        new_refresh_token = response.get('refresh_token')
        if new_refresh_token:
            account.refresh_token = new_refresh_token
        else:
            if (len(account.valid_auth_credentials) == 0 or
                    account.sync_state == 'invalid'):
                # We got a new auth without a refresh token, so we need to back
                # out and force the auth flow, since we don't already have
                # a refresh (or the ones we have don't work.)
                raise OAuthError("No valid refresh tokens")

        account.email_address = email_address
        account.family_name = response.get('family_name')
        account.given_name = response.get('given_name')
        account.name = response.get('name')
        account.gender = response.get('gender')
        account.g_id = response.get('id')
        account.g_user_id = response.get('user_id')
        account.link = response.get('link')
        account.locale = response.get('locale')
        account.picture = response.get('picture')
        account.home_domain = response.get('hd')
        account.sync_contacts = (account.sync_contacts or
                                 response.get('contacts', True))
        account.sync_events = (account.sync_events or
                               response.get('events', True))

        # These values are deprecated and should not be used, along
        # with the account's refresh_token. Access all these values
        # through the GmailAuthCredentials objects instead.
        account.client_id = response.get('client_id')
        account.client_secret = response.get('client_secret')
        account.scope = response.get('scope')
        account.g_id_token = response.get('id_token')

        # Don't need to actually save these now
        # tok = response.get('access_token')
        # expires_in = response.get('expires_in')

        client_id = response.get('client_id') or OAUTH_CLIENT_ID
        client_secret = response.get('client_secret') or OAUTH_CLIENT_SECRET

        if new_refresh_token:
            # See if we already have credentials for this client_id/secret
            # pair. If those don't exist, make a new GmailAuthCredentials
            auth_creds = next(
                (auth_creds for auth_creds in account.auth_credentials
                 if (auth_creds.client_id == client_id and
                     auth_creds.client_secret == client_secret)),
                GmailAuthCredentials())

            auth_creds.gmailaccount = account
            auth_creds.scopes = response.get('scope')
            auth_creds.g_id_token = response.get('id_token')
            auth_creds.client_id = client_id
            auth_creds.client_secret = client_secret
            auth_creds.refresh_token = new_refresh_token
            auth_creds.is_valid = True

            db_session.add(auth_creds)

        try:
            self.verify_config(account)
        except GmailSettingError as e:
            raise UserRecoverableConfigError(e)

        # Ensure account has sync enabled.
        account.enable_sync()

        return account

    def validate_token(self, access_token):
        response = requests.get(self.OAUTH_TOKEN_VALIDATION_URL,
                                params={'access_token': access_token})
        validation_dict = response.json()

        if 'error' in validation_dict:
            raise OAuthError(validation_dict['error'])

        return validation_dict

    def verify_config(self, account):
        """Verifies configuration, specifically presence of 'All Mail' folder.
           Will raise an inbox.crispin.GmailSettingError if not present.
        """
        conn = self.connect_account(account)
        # make a crispin client and check the folders
        client = GmailCrispinClient(account.id,
                                    provider_info('gmail'),
                                    account.email_address,
                                    conn,
                                    readonly=True)
        client.sync_folders()
        conn.logout()
        return True

    def interactive_auth(self, email_address=None):
        url_args = {'redirect_uri': self.OAUTH_REDIRECT_URI,
                    'client_id': self.OAUTH_CLIENT_ID,
                    'response_type': 'code',
                    'scope': self.OAUTH_SCOPE,
                    'access_type': 'offline'}
        if email_address:
            url_args['login_hint'] = email_address
        url = url_concat(self.OAUTH_AUTHENTICATE_URL, url_args)

        print 'To authorize Inbox, visit this URL and follow the directions:'
        print '\n{}'.format(url)

        while True:
            auth_code = raw_input('Enter authorization code: ').strip()
            try:
                auth_response = self._get_authenticated_user(auth_code)
                auth_response['contacts'] = True
                auth_response['events'] = True
                return auth_response
            except OAuthError:
                print "\nInvalid authorization code, try again...\n"
                auth_code = None
