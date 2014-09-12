import datetime
from inbox.log import get_logger
logger = get_logger()

from inbox.events.google import GoogleEventsProvider
from inbox.events.outlook import OutlookEventsProvider
from inbox.events.icloud import ICloudEventsProvider
from inbox.sync.base_sync import BaseSync
from inbox.models import Event

__provider_map__ = {'gmail': GoogleEventsProvider,
                    'outlook': OutlookEventsProvider,
                    'icloud': ICloudEventsProvider}

__provider_poll_frequency__ = {'outlook': 1500}


class EventSync(BaseSync):
    """Per-account event sync engine.

    Parameters
    ----------
    account_id: int
        The ID for the user account for which to fetch event data.

    poll_frequency: int
        In seconds, the polling frequency for querying the events provider
        for updates.

    Attributes
    ---------
    log: logging.Logger
        Logging handler.
    """
    def __init__(self, provider_name, account_id, poll_frequency=None):
        if poll_frequency is None:
            poll_frequency = __provider_poll_frequency__.get(provider_name,
                                                             300)

        self._provider_name = provider_name
        self.log = logger.new(account_id=account_id, component='event sync')
        self.log.info('Begin syncing Events...')

        BaseSync.__init__(self, account_id, poll_frequency)

    @property
    def provider(self):
        return __provider_map__[self._provider_name]

    @property
    def target_obj(self):
        return Event

    def last_sync(self, account):
        return account.last_synced_events

    def set_last_sync(self, account):
        account.last_synced_events = datetime.datetime.now()
