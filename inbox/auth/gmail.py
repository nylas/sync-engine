import requests
from sqlalchemy.orm.exc import NoResultFound

from inbox.models import Namespace
from inbox.models.backends.gmail import GmailAccount
from inbox.config import config
from inbox.auth.oauth import OAuthAuthHandler
from inbox.basicauth import (OAuthValidationError, OAuthError,
                             UserRecoverableConfigError)
from inbox.util.url import url_concat
from inbox.providers import provider_info
from inbox.crispin import GmailCrispinClient, GmailSettingError

from inbox.log import get_logger
log = get_logger()

PROVIDER = 'gmail'

# Google OAuth app credentials
OAUTH_CLIENT_ID = config.get_required('GOOGLE_OAUTH_CLIENT_ID')
OAUTH_CLIENT_SECRET = config.get_required('GOOGLE_OAUTH_CLIENT_SECRET')
OAUTH_REDIRECT_URI = config.get_required('GOOGLE_OAUTH_REDIRECT_URI')

OAUTH_AUTHENTICATE_URL = 'https://accounts.google.com/o/oauth2/auth'
OAUTH_ACCESS_TOKEN_URL = 'https://accounts.google.com/o/oauth2/token'
OAUTH_TOKEN_VALIDATION_URL = 'https://www.googleapis.com/oauth2/v1/tokeninfo'
OAUTH_USER_INFO_URL = 'https://www.googleapis.com/oauth2/v1/userinfo'

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

        tok = response.get('access_token')
        expires_in = response.get('expires_in')
        account.set_access_token(tok, expires_in)
        account.scope = response.get('scope')
        account.email_address = email_address
        account.family_name = response.get('family_name')
        account.given_name = response.get('given_name')
        account.name = response.get('name')
        account.gender = response.get('gender')
        account.g_id = response.get('id')
        account.g_user_id = response.get('user_id')
        account.g_id_token = response.get('id_token')
        account.link = response.get('link')
        account.locale = response.get('locale')
        account.picture = response.get('picture')
        account.home_domain = response.get('hd')
        account.client_id = response.get('client_id')
        account.client_secret = response.get('client_secret')
        account.sync_contacts = response.get('contacts', True)
        account.sync_events = response.get('events', True)

        try:
            self.verify_config(account)
        except GmailSettingError as e:
            raise UserRecoverableConfigError(e)

        # Hack to ensure that account syncs get restarted if they were stopped
        # because of e.g. invalid credentials and the user re-auths.
        # TODO(emfree): remove after status overhaul.
        if account.sync_state != 'running':
            account.sync_state = None

        return account

    def validate_token(self, access_token):
        response = requests.get(self.OAUTH_TOKEN_VALIDATION_URL,
                                params={'access_token': access_token})
        validation_dict = response.json()

        if 'error' in validation_dict:
            raise OAuthValidationError(validation_dict['error'])

        return validation_dict

    def verify_config(self, account):
        """Verifies configuration, specifically presence of 'All Mail' folder.
           Will raise an inbox.crispin.GmailSettingError if not present.
        """
        conn = self.connect_account(account.email_address,
                                    account.access_token,
                                    account.imap_endpoint)
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
