from inbox.util.url import provider_from_address, NotSupportedError
from inbox.util.misc import load_modules
from inbox.auth.oauth import (validate_token, get_new_token,
                              InvalidOAuthGrantError)
from inbox.log import get_logger
log = get_logger()

import inbox.auth

AUTH_MOD_FOR = {}


def register_backends():
    """
    Finds the auth modules for the different providers
    (in the backends directory) and imports them.

    Creates a mapping of provider:auth_cls for each backend found.
    """
    # Find and import
    modules = load_modules(inbox.auth)

    # Create mapping
    for module in modules:
        if hasattr(module, 'PROVIDER'):
            provider = module.PROVIDER
            AUTH_MOD_FOR[provider] = module


def get_handler(email_address):
    register_backends()

    provider = provider_from_address(email_address)
    auth_mod = AUTH_MOD_FOR.get(provider)

    if auth_mod is not None:
        return auth_mod

    # Try as EAS
    auth_mod = AUTH_MOD_FOR.get('eas', None)
    if auth_mod is not None:
        return auth_mod

    raise NotSupportedError('Inbox does not support the email provider.')


def verify_imap_account(db_session, account):
    # issued_date = credentials.date
    # expires_seconds = credentials.o_expires_in

    # TODO check with expire date first
    # expire_date = issued_date + datetime.timedelta(seconds=expires_seconds)

    auth_handler = get_handler(account.email_address)

    is_valid = validate_token(account.access_token)

    # TODO refresh tokens based on date instead of checking?
    # if not is_valid or expire_date > datetime.datetime.utcnow():
    if not is_valid:
        log.error('Need to update access token!')

        refresh_token = account.refresh_token

        log.error('Getting new access token...')

        try:
            response = get_new_token(refresh_token)
        # Redo the entire OAuth process.
        except InvalidOAuthGrantError:
            account = auth_handler.create_auth_account(db_session,
                                                       account.email_address)
            return auth_handler.verify_account(db_session, account)

        response['refresh_token'] = refresh_token  # Propogate it through

        # TODO handling errors here for when oauth has been revoked

        # TODO Verify it and make sure it's valid.
        assert 'access_token' in response

        account = auth_handler.create_account(db_session,
                                              account.email_address, response)
        log.info('Updated token for imap account {0}'.format(
            account.email_address))

    return account
