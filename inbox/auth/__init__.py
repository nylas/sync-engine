"""
Per-provider auth modules.

An auth module *must* meet the following requirement:

1. Specify the provider it implements as the module-level PROVIDER variable.
For example, 'gmail', 'imap', 'eas', 'yahoo' etc.

2. Live in the 'auth/' directory.

3. Register an AuthHandler class as an entry point in setup.py
"""
# Allow out-of-tree auth submodules.
from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)

from inbox.util.misc import register_backends

import pkg_resources
from abc import ABCMeta, abstractmethod
from inbox.providers import providers
from inbox.util.url import provider_from_address
from inbox.basicauth import NotSupportedError


def handler_from_provider(provider_name):
    """Return an authentication handler for the given provider.

    Parameters
    ----------
    provider_name : str
        Name of the email provider (e.g. inbox/providers.py) OR of the provider
        module's PROVIDER constant

        (XXX: interface terribleness!)

    Returns
    -------
    An object that implements the AuthHandler interface.

    Note that if a plugin provides mixin classes, the type of the object may be
    generated dynamically, and may not necessarily be directly importable.
    """

    # TODO: Console auth doesn't have support for handling unknown providers
    # and just trying eas first with a fallback, so just assume EAS for now.
    # -cg3
    if provider_name == 'unknown':
        provider_name = 'eas'
    auth_mod = module_registry.get(provider_name)

    if auth_mod is None:
        # Try to get a generic provider
        info = providers.get(provider_name, None)
        if info:
            provider_type = info.get('type', None)
            if provider_type:
                auth_mod = module_registry.get('generic')

    if auth_mod is None:
        raise NotSupportedError('Inbox does not support the email provider.')

    # The name in the entry_point must match module's PROVIDER constant.
    # Known values include: 'generic', 'gmail', 'outlook', 'eas' (if installed)
    mod_name = auth_mod.PROVIDER

    # Now get the AuthHandler corresponding to the auth_mod.
    # XXX: We should replace register_backends with entry_points.
    auth_handler_class = None
    group = 'inbox.auth'
    for entry_point in pkg_resources.iter_entry_points(group, mod_name):
        if auth_handler_class is not None:
            raise RuntimeError(
                "Duplicate definition of inbox.auth handler: {0!r}".format(
                    mod_name))
        auth_handler_class = entry_point.load()

    assert auth_handler_class is not None, \
        "auth module {} not registered as an entry point".format(mod_name)

    # Allow plugins to specify mixin classes
    # Example usage:
    #
    #   # setup.py snippet
    #   entry_points = {
    #       'inbox.auth.mixins': [
    #           'yahoo = example.auth:YAuthMixin',
    #           '* = example.auth:AllAuthMixin',
    #       ],
    #   },
    #
    #   # example/auth.py
    #
    #   class YAuthMixin(object):
    #       def verify_account(self, account):
    #           if account.email == 'forbiddenuser@yahoo.com':
    #               return False
    #           return super(YAuthMixin, self).verify_account(account)
    #
    mixins = []
    group = 'inbox.auth.mixins'
    for entry_point in pkg_resources.iter_entry_points(group, '*'):
        mixins.append(entry_point.load())
    for entry_point in pkg_resources.iter_entry_points(group, mod_name):
        mixins.append(entry_point.load())

    if mixins:
        bases = tuple(mixins) + (auth_handler_class,)

        # type(name, bases, dict)
        auth_handler_class = type(
            '<wrapped %s>' % auth_handler_class.__name__,
            bases,
            {})

    auth_handler = auth_handler_class()
    return auth_handler


def handler_from_email(email_address):
    if '@mit.edu' in email_address:
        user, domain = email_address.split('@')
        email_address = user + '@exchange.mit.edu'

    provider_name = provider_from_address(email_address)
    return handler_from_provider(provider_name)


class AuthHandler(object):
    __metaclass__ = ABCMeta

    # optional
    def connect_account(self, provider, email, secret):
        """Return an authenticated IMAPClient instance for the given credentials.

        This is an optional interface, which is only needed for accounts that
        are synced using IMAP.
        """
        raise NotImplementedError

    @abstractmethod
    def create_account(self, db_session, email_address, response):
        raise NotImplementedError

    @abstractmethod
    def create_auth_account(self, db_session, email_address, token, exit):
        raise NotImplementedError

    @abstractmethod
    def verify_account(self, account):
        raise NotImplementedError


# Load the other inbox.auth.* modules
module_registry = register_backends(__name__, __path__)
