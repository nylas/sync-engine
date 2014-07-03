from inbox.util.url import provider_from_address, NotSupportedError
from inbox.util.misc import load_modules
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
    if AUTH_MOD_FOR:
        return

    # Find and import
    modules = load_modules(inbox.auth)

    # Create mapping
    for module in modules:
        if hasattr(module, 'PROVIDER'):
            provider = module.PROVIDER
            AUTH_MOD_FOR[provider] = module


def handler_from_provider(provider):
    register_backends()
    auth_mod = AUTH_MOD_FOR.get(provider)

    if auth_mod is not None:
        return auth_mod

    # Try as EAS
    auth_mod = AUTH_MOD_FOR.get('eas', None)
    if auth_mod is not None:
        return auth_mod

    raise NotSupportedError('Inbox does not support the email provider.')


def handler_from_email(email_address):
    return handler_from_provider(provider_from_address(email_address))
