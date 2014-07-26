"""
Per-provider auth modules.

An auth module *must* meet the following requirement:

1. Specify the provider it implements as the module-level PROVIDER variable.
For example, 'gmail', 'imap', 'eas', 'yahoo' etc.

2. Live in the 'auth/' directory.
"""
# Allow out-of-tree auth submodules.
from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)

from inbox.util.misc import register_backends

module_registry = register_backends(__name__, __path__)

from inbox.util.url import provider_from_address
from inbox.basicauth import NotSupportedError


def handler_from_provider(provider):
    auth_mod = module_registry.get(provider)

    if auth_mod is not None:
        return auth_mod

    raise NotSupportedError('Inbox does not support the email provider.')


def handler_from_email(email_address):
    if '@mit.edu' in email_address:
        user, domain = email_address.split('@')
        email_address = user + '@exchange.mit.edu'
    return handler_from_provider(provider_from_address(email_address))
