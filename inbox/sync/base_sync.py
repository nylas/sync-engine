import gevent
import datetime
from collections import Counter

from inbox.log import get_logger
logger = get_logger()

from inbox.basicauth import ValidationError
from inbox.models.session import session_scope
from inbox.util.concurrency import retry_with_logging
from inbox.util.misc import or_none
from inbox.models import Account


class BaseSync(gevent.Greenlet):
    def __init__(self, account_id, poll_frequency):
        self.account_id = account_id
        self.poll_frequency = poll_frequency

        gevent.Greenlet.__init__(self)

    def _run(self):
        return retry_with_logging(self._run_impl, self.log)

    def _run_impl(self):
        try:
            self.provider_instance = self.provider(self.account_id)
            while True:
                self.poll()
                gevent.sleep(self.poll_frequency)
        except ValidationError:
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

    @property
    def merge_attrs(self):
        raise NotImplementedError  # Implement in subclasses

    def last_sync(self, account):
        raise NotImplementedError  # Implement in subclasses

    def poll(self):
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

        log = logger.new(account_id=self.account_id)
        provider_name = self.provider_instance.PROVIDER_NAME
        with session_scope() as db_session:
            account = db_session.query(Account).get(self.account_id)
            change_counter = Counter()
            last_sync = or_none(self.last_sync(account),
                                datetime.datetime.isoformat)
            to_commit = []
            for item in self.provider_instance.get_items(last_sync):
                item.account = account
                assert item.uid is not None, \
                    'Got remote item with null uid'
                assert isinstance(item.uid, str)

                target_obj = self.target_obj
                matching_items = db_session.query(target_obj).filter(
                    target_obj.account == account,
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
                            self.merge(cached_item, item, local_item)
                            # And update cached_item to reflect both local and
                            # remote updates
                            cached_item.copy_from(local_item)

                        except MergeError:
                            log.error('Conflicting local and remote updates'
                                      'to item.',
                                      local=local_item, cached=cached_item,
                                      remote=item)
                            # For now, just don't update if conflict ing
                            continue
                    else:
                        log.warning('Item already present as remote but not '
                                    'local item', cached_item=cached_item)
                        cached_item.copy_from(item)
                    change_counter['updated'] += 1
                else:
                    # This is a new item, create both local and remote DB
                    # entries.
                    local_item = self.target_obj()
                    local_item.copy_from(item)
                    local_item.source = 'local'
                    to_commit.append(item)
                    to_commit.append(local_item)
                    change_counter['added'] += 1

            self.set_last_sync(account)

            log.info('sync', added=change_counter['added'],
                     updated=change_counter['updated'],
                     deleted=change_counter['deleted'])

            db_session.add_all(to_commit)
            db_session.commit()

    def merge(self, base, remote, dest):
        """Merge changes from remote into dest if there are no conflicting
        updates to remote and dest relative to base.

        Parameters
        ----------
        base, remote, dest: target object type

        Raises
        ------
        MergeError
            If there is a conflict.
        """
        for attr_name in self.merge_attrs:
            base_attr = getattr(base, attr_name)
            remote_attr = getattr(remote, attr_name)
            dest_attr = getattr(dest, attr_name)
            if base_attr != remote_attr != dest_attr != base_attr:
                raise MergeError('Conflicting updates to items {0}, {1} from '
                                 'base {2} on attr: {3}'.format(remote,
                                                                dest,
                                                                base,
                                                                attr_name))

        # No conflicts, can merge
        for attr_name in self.merge_attrs:
            base_attr = getattr(base, attr_name)
            remote_attr = getattr(remote, attr_name)
            if base_attr != remote_attr:
                setattr(dest, attr_name, remote_attr)


class MergeError(Exception):
    pass
