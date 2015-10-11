from abc import ABCMeta, abstractmethod

from sqlalchemy.orm.exc import NoResultFound

from inbox.models.session import session_scope
from inbox.providers import providers
from inbox.basicauth import NotSupportedError


def handler_from_provider(provider_name):
    """
    Return an authentication handler for the given provider.

    Parameters
    ----------
    provider_name : str
        Name of the email provider (e.g. inbox/providers.py) OR of the provider
        module's PROVIDER constant

        (XXX: interface terribleness!)

    Returns
    -------
    An object that implements the AuthHandler interface.

    """
    from inbox.auth import module_registry
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

    auth_handler_class = getattr(auth_mod, auth_mod.AUTH_HANDLER_CLS)
    auth_handler = auth_handler_class(provider_name=provider_name)
    return auth_handler


def account_or_none(target, cls, email_address):
    """
    Query the target shard to determine if an account with the given provider
    (as determined by the model cls to query) and email_address exists.

    Parameters
    ----------
        cls:
            Account model to query.
            (GenericAccount/ GmailAccount/ EASAccount)
        email_address:
            Email address to query for.

    Returns
    -------
        The Account if such an account exists, else None.

    """
    shard_id = target << 48
    with session_scope(shard_id) as db_session:
        try:
            account = db_session.query(cls).filter(
                cls.email_address == email_address).one()
        except NoResultFound:
            return
        db_session.expunge(account)
    return account


class AuthHandler(object):
    __metaclass__ = ABCMeta

    def __init__(self, provider_name):
        self.provider_name = provider_name

    # Optional
    def connect_account(self, account):
        """
        Return an authenticated IMAPClient instance for the given account.

        This is an optional interface, which is only needed for accounts that
        are synced using IMAP.

        """
        raise NotImplementedError

    @abstractmethod
    def get_account(self, target, email_address, response):
        """
        Return an account for the provider and email_address.
        This method is a wrapper around create_account() and update_account();
        it creates a new account if necessary, else updates the existing one.

        """
        raise NotImplementedError

    @abstractmethod
    def create_account(self, email_address, response):
        """
        Create a new account.
        This method does NOT check for the existence of an account for a
        provider and email_address. That should be done by the caller.

        """
        raise NotImplementedError

    @abstractmethod
    def update_account(self, account, response):
        """
        Update an existing account with the params in response.
        This method assumes the existence of the account passed in.

        """
        raise NotImplementedError

    @abstractmethod
    def verify_account(self, account):
        raise NotImplementedError

    @abstractmethod
    def interactive_auth(self, email_address=None):
        raise NotImplementedError
