import gevent
import gevent.event
from datetime import datetime
from collections import Counter

from inbox.log import get_logger
logger = get_logger()

from inbox.basicauth import ConnectionError, ValidationError, PermissionsError
from inbox.models.session import session_scope
from inbox.util.concurrency import retry_with_logging
from inbox.util.misc import MergeError
from inbox.models import Account
from inbox.status.sync import SyncStatus


class BaseSync(gevent.Greenlet):
    def __init__(self, account_id, namespace_id, poll_frequency, folder_id,
                 folder_name, provider_name):
        self.shutdown = gevent.event.Event()
        self.account_id = account_id
        self.namespace_id = namespace_id
        self.poll_frequency = poll_frequency
        self.log = logger.new(account_id=account_id)
        self.folder_id = folder_id
        self.folder_name = folder_name
        self._provider_name = provider_name
        self.sync_status = SyncStatus(self.account_id, self.folder_id)
        self.sync_status.publish(provider_name=self._provider_name,
                                 folder_name=self.folder_name)

        gevent.Greenlet.__init__(self)

    def _run(self):
        return retry_with_logging(self._run_impl, self.log,
                                  account_id=self.account_id)

    def _run_impl(self):
        try:
            self.provider_instance = self.provider(self.account_id,
                                                   self.namespace_id)
            while True:
                # Check to see if this greenlet should exit
                if self.shutdown.is_set():
                    return False

                try:
                    self.poll()
                    self.sync_status.publish(state='poll')

                # If we get a connection or API permissions error, then sleep
                # 2x poll frequency.
                except (ConnectionError, PermissionsError):
                    self.sync_status.publish(state='poll error')
                    gevent.sleep(self.poll_frequency)
                gevent.sleep(self.poll_frequency)
        except ValidationError:
            # Bad account credentials; exit.
            return False

    @property
    def target_obj(self):
        raise NotImplementedError  # return Contact or Event

    @property
    def provider(self):
        raise NotImplementedError  # Implement in subclasses

    @property
    def provider_name(self):
        raise NotImplementedError  # Implement in subclasses

    def last_sync(self, account):
        raise NotImplementedError  # Implement in subclasses

    def poll(self):
        return base_poll(self.account_id, self.provider_instance,
                         self.last_sync, self.target_obj,
                         self.set_last_sync)


def base_poll(account_id, provider_instance, last_sync_fn, target_obj,
              set_last_sync_fn):
    """Query a remote provider for updates and persist them to the
    database.

    Parameters
    ----------
    account_id: int
        ID for the account whose items should be queried.
    db_session: sqlalchemy.orm.session.Session
        Database session

    provider: Interface to the remote item data provider.
        Must have a PROVIDER_NAME attribute and implement the get()
        method.
    """
    # Get a timestamp before polling, so that we don't subsequently miss remote
    # updates that happen while the poll loop is executing.
    sync_timestamp = datetime.utcnow()

    log = logger.new(account_id=account_id)
    provider_name = provider_instance.PROVIDER_NAME
    with session_scope() as db_session:
        account = db_session.query(Account).get(account_id)
        last_sync = None
        if last_sync_fn(account) is not None:
            # Note explicit offset is required by e.g. Google calendar API.
            last_sync = datetime.isoformat(last_sync_fn(account)) + 'Z'

    items = provider_instance.get_items(last_sync)
    with session_scope() as db_session:
        account = db_session.query(Account).get(account_id)
        change_counter = Counter()
        for item in items:
            item.namespace = account.namespace
            assert item.uid is not None, \
                'Got remote item with null uid'
            assert isinstance(item.uid, str)

            target_obj = target_obj
            matching_items = db_session.query(target_obj).filter(
                target_obj.namespace == account.namespace,
                target_obj.provider_name == provider_name,
                target_obj.uid == item.uid)
            # Snapshot of item data from immediately after last sync:
            cached_item = matching_items. \
                filter(target_obj.source == 'remote').first()

            # Item data reflecting any local modifications since the last
            # sync with the remote provider:
            local_item = matching_items. \
                filter(target_obj.source == 'local').first()
            # If the remote item was deleted, purge the corresponding
            # database entries.
            if item.deleted:
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
                        local_item.merge_from(cached_item, item)
                        # And update cached_item to reflect both local and
                        # remote updates
                        cached_item.copy_from(local_item)

                    except MergeError:
                        log.error('Conflicting local and remote updates '
                                  'to item.',
                                  local=local_item, cached=cached_item,
                                  remote=item)
                        # For now, just don't update if conflicting
                        continue
                else:
                    log.warning('Item already present as remote but not '
                                'local item', cached_item=cached_item)
                    cached_item.copy_from(item)
                change_counter['updated'] += 1
            else:
                # This is a new item, create both local and remote DB
                # entries.
                local_item = target_obj()
                local_item.copy_from(item)
                local_item.source = 'local'
                db_session.add_all([item, local_item])
                db_session.flush()
                change_counter['added'] += 1

        set_last_sync_fn(account, sync_timestamp)

        log.info('sync', added=change_counter['added'],
                 updated=change_counter['updated'],
                 deleted=change_counter['deleted'])

        db_session.commit()
