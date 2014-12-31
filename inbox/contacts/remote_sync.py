from inbox.log import get_logger
logger = get_logger()
from inbox.models import Contact
from inbox.contacts.google import GoogleContactsProvider
from inbox.sync.base_sync import BaseSync
from inbox.util.debug import bind_context

__provider_map__ = {'gmail': GoogleContactsProvider}


class ContactSync(BaseSync):
    """
    Per-account contact sync engine.

    Parameters
    ----------
    account_id: int
        The ID for the user account for which to fetch contact data.

    poll_frequency: int
        In seconds, the polling frequency for querying the contacts provider
        for updates.

    Attributes
    ---------
    log: logging.Logger
        Logging handler.

    """
    def __init__(self, provider_name, account_id, namespace_id,
                 poll_frequency=300):
        bind_context(self, 'contactsync', account_id)
        self.log = logger.new(account_id=account_id, component='contact sync')
        self.log.info('Begin syncing contacts...')

        BaseSync.__init__(self, account_id, namespace_id, poll_frequency, -1,
                          'Contacts', provider_name)

    @property
    def provider(self):
        return __provider_map__[self._provider_name]

    @property
    def target_obj(self):
        return Contact

    def last_sync(self, account):
        return account.last_synced_contacts

    def set_last_sync(self, account, dt):
        account.last_synced_contacts = dt
