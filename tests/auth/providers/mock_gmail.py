""" Mock provider which triggers failure at a specific step of the
    authentication process depending on email entered.
    Note that this uses live Gmail authentication, so auth should be called
    using real email addresses with + parameters, eg.
    foobar+no_all_mail@gmail.com.

    * Gmail All Mail folder missing
    * Gmail Trash folder missing
    * OAuth error during scope acceptance
"""

from inbox.models import Namespace
from inbox.models.backends.gmail import GmailAccount

from inbox.auth.gmail import GmailAuthHandler
from inbox.crispin import GmailSettingError
from inbox.basicauth import OAuthError, UserRecoverableConfigError

from inbox.log import get_logger
log = get_logger()

PROVIDER = 'gmail'  # Uses the default gmail provider info from providers.py
AUTH_HANDLER_CLS = 'MockGmailAuthHandler'


def raise_setting_error(folder):
    raise GmailSettingError(folder)


def raise_oauth_error(e):
    raise OAuthError(e)


fake_responses = {
    'no_all_mail': raise_setting_error,
    'no_trash': raise_setting_error,
    'oauth_fail': raise_oauth_error
}


class MockGmailAuthHandler(GmailAuthHandler):

    def create_account(self, db_session, email_address, response):
        # Override create_account to persist the 'login hint' email_address
        # rather than the canonical email that is contained in response.
        # This allows us to trigger errors by authing with addresses of the
        # format:
        #    foobar+no_all_mail@gmail.com

        # Since verify_config throws an Exception if no specific case is
        # triggered, this account is never committed.
        namespace = Namespace()
        account = GmailAccount(namespace=namespace)
        account.email_address = email_address

        try:
            self.verify_config(account)
        except GmailSettingError as e:
            print e
            raise UserRecoverableConfigError(e)

        return account

    def verify_config(self, account):
        for key, response in fake_responses.iteritems():
            if key in account.email_address:
                return response(key)
        # Raise an exception to prevent committing test accounts
        raise Exception("Auth succeeded")
