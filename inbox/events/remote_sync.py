from datetime import datetime
from collections import Counter

from inbox.log import get_logger
logger = get_logger()

from inbox.sync.base_sync import BaseSyncMonitor
from inbox.models import Event, Account
from inbox.util.debug import bind_context
from inbox.models.session import session_scope
from inbox.basicauth import ValidationError
from inbox.util.misc import MergeError

from inbox.events.google import GoogleEventsProvider
from inbox.events.outlook import OutlookEventsProvider
from inbox.events.icloud import ICloudEventsProvider

EVENT_SYNC_PROVIDER_MAP = {'gmail': GoogleEventsProvider,
                           'outlook': OutlookEventsProvider,
                           'icloud': ICloudEventsProvider}


EVENT_SYNC_FOLDER_ID = -2
EVENT_SYNC_FOLDER_NAME = 'Events'


class EventSync(BaseSyncMonitor):
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
    def __init__(self, email_address, provider_name, account_id, namespace_id,
                 poll_frequency=300):
        bind_context(self, 'eventsync', account_id)
        self.log = logger.new(account_id=account_id, component='event sync')
        self.log.info('Begin syncing Events...')

        self.provider_name = provider_name

        self.folder_id = EVENT_SYNC_FOLDER_ID
        self.folder_name = EVENT_SYNC_FOLDER_NAME
        self.email_address = email_address

        provider_cls = EVENT_SYNC_PROVIDER_MAP[self.provider_name]
        self.provider = provider_cls(account_id, namespace_id)

        BaseSyncMonitor.__init__(self,
                                 account_id,
                                 namespace_id,
                                 EVENT_SYNC_FOLDER_ID,
                                 poll_frequency=poll_frequency,
                                 retry_fail_classes=[ValidationError])

    def sync(self):
        """Query a remote provider for updates and persist them to the
        database. This function runs every `self.poll_frequency`.

        """
        # Grab timestamp so next sync gets deltas from now
        sync_timestamp = datetime.utcnow()

        with session_scope() as db_session:
            account = db_session.query(Account).get(self.account_id)
            last_sync_dt = account.last_synced_contacts

            all_events = self.provider.get_items(sync_from_dt=last_sync_dt)

            change_counter = Counter()
            for new_event in all_events:

                new_event.namespace = account.namespace
                # TODO remove these checks
                assert new_event.uid is not None, \
                    'Got remote item with null uid'
                assert isinstance(new_event.uid, basestring)

                events_query = db_session.query(Event).filter(
                    Event.namespace_id == self.namespace_id,
                    Event.provider_name == self.provider.PROVIDER_NAME,
                    Event.uid == new_event.uid)

                # Snapshot of item data from immediately after last sync:
                cached_item = events_query. \
                    filter(Event.source == 'remote').first()

                # Item data reflecting any local modifications since the last
                # sync with the remote provider:
                local_item = events_query. \
                    filter(Event.source == 'local').first()

                if new_event.deleted:
                    if cached_item is not None:
                        db_session.delete(cached_item)
                        change_counter['deleted'] += 1
                    if local_item is not None:
                        db_session.delete(local_item)
                    continue
                # Otherwise, update the database.
                if cached_item is not None:
                    # The provider gave an update to a item we already have.
                    if local_item is not None:
                        try:
                            # Attempt to merge remote updates into local_item
                            local_item.merge_from(cached_item, new_event)
                            # And update cached_item to reflect both local and
                            # remote updates
                            cached_item.copy_from(local_item)

                        except MergeError:
                            self.log.error(
                                'Conflicting local and remote updates to '
                                'item.', local=local_item, cached=cached_item,
                                remote=new_event)
                            # For now, just don't update if conflicting
                            continue
                    else:
                        self.log.warning(
                            'event is already present as remote but not local '
                            'item', cached_item=cached_item)
                        cached_item.copy_from(new_event)
                    change_counter['updated'] += 1
                else:
                    # This is a new item, create both local and remote DB
                    # entries.
                    local_item = Event()
                    local_item.copy_from(new_event)
                    local_item.source = 'local'
                    db_session.add_all([new_event, local_item])
                    db_session.flush()
                    change_counter['added'] += 1

        # Set last full sync date upon completion
        with session_scope() as db_session:
            account = db_session.query(Account).get(self.account_id)
            account.last_synced_events = sync_timestamp

        self.log.info('sync', added=change_counter['added'],
                      updated=change_counter['updated'],
                      deleted=change_counter['deleted'])
