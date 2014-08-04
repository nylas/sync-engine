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

from inbox.providers import providers
from inbox.util.url import provider_from_address
from inbox.basicauth import NotSupportedError


def handler_from_provider(provider_name):
    # TODO: Console auth doesn't have support for handling unknown providers
    # and just trying eas first with a fallback, so just assume EAS for now.
    # -cg3
    if provider_name == 'unknown':
        provider_name = 'eas'
    auth_mod = module_registry.get(provider_name)

    if auth_mod is not None:
        return auth_mod

    # Try to get a generic provider
    info = providers.get(provider_name, None)
    if info:
        provider_type = info.get('type', None)
        if provider_type:
            auth_mod = module_registry.get('generic')

            if auth_mod is not None:
                return auth_mod

    raise NotSupportedError('Inbox does not support the email provider.')


def handler_from_email(email_address):
    if '@mit.edu' in email_address:
        user, domain = email_address.split('@')
        email_address = user + '@exchange.mit.edu'

    provider_name = provider_from_address(email_address)
    return handler_from_provider(provider_name)
