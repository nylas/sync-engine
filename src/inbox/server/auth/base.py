import sys

from inbox.util.url import provider_from_address, NotSupportedError
from inbox.util.misc import load_modules
from inbox.server.log import get_logger
log = get_logger()

import inbox.server.auth

AUTH_MOD_FOR = {}


def register_backends():
    """
    Finds the auth modules for the different providers
    (in the backends directory) and imports them.

    Creates a mapping of provider:auth_cls for each backend found.
    """
    # Find and import
    modules = load_modules(inbox.server.auth)

    # Create mapping
    for module in modules:
        if getattr(module, 'PROVIDER', None) is not None:
            provider = module.PROVIDER
            AUTH_MOD_FOR[provider] = module


def get_handler(email_address):
    register_backends()

    provider = provider_from_address(email_address)
    auth_mod = AUTH_MOD_FOR.get(provider)

    if auth_mod is None:
        raise NotSupportedError('Inbox currently only supports Gmail and Yahoo.')
        sys.exit(1)

    return auth_mod


def commit_account(db_session, account):
    db_session.add(account)
    db_session.commit()

    log.info("Stored new account {0}".format(account.email_address))
