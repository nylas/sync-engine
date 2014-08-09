import datetime

from inbox.log import get_logger
logger = get_logger()

from inbox.events.google import GoogleEventsProvider
from inbox.sync.base_sync import BaseSync
from inbox.models import Event


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
    def __init__(self, account_id, poll_frequency=300):
        self.log = logger.new(account_id=account_id, component='event sync')
        self.log.info('Begin syncing Events...')

        BaseSync.__init__(self, account_id, poll_frequency)

    @property
    def provider(self):
        return GoogleEventsProvider

    @property
    def merge_attrs(self):
        # This must be updated when new fields are added to the class.
        return ['subject', 'body', 'start', 'end', 'all_day',
                'locked', 'location', 'reminders', 'recurrence',
                'time_zone', 'busy', 'raw_data']

    @property
    def target_obj(self):
        return Event

    def last_sync(self, account):
        return account.last_synced_events

    def set_last_sync(self, account):
        account.last_synced_events = datetime.datetime.now()
