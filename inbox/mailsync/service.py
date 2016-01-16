import platform

import gevent
from gevent.lock import BoundedSemaphore
from sqlalchemy.exc import OperationalError

from inbox.providers import providers
from inbox.config import config
from inbox.contacts.remote_sync import ContactSync
from inbox.events.remote_sync import EventSync, GoogleEventSync
from inbox.heartbeat.status import clear_heartbeat_status
from nylas.logging import get_logger
from nylas.logging.sentry import log_uncaught_errors
from inbox.ignition import engine_manager
from inbox.models.session import session_scope, session_scope_by_shard_id
from inbox.models import Account
from inbox.util.concurrency import retry_with_logging
from inbox.util.stats import statsd_client

from inbox.mailsync.backends import module_registry

USE_GOOGLE_PUSH_NOTIFICATIONS = \
    'GOOGLE_PUSH_NOTIFICATIONS' in config.get('FEATURE_FLAGS', [])


class SyncService(object):
    """
    Parameters
    ----------
    cpu_id : int
        If a system has 4 cores, value from 0-3. (Each sync service on the
        system should get a different value.)
    total_cpus : int
        Total CPUs on the system.
    poll_interval : int
        Seconds between polls for account changes.
    """
    def __init__(self, process_identifier, cpu_id, total_cpus,
                 poll_interval=10):
        self.host = platform.node()
        self.cpu_id = cpu_id
        self.process_identifier = process_identifier
        self.total_cpus = total_cpus
        self.monitor_cls_for = {mod.PROVIDER: getattr(
            mod, mod.SYNC_MONITOR_CLS) for mod in module_registry.values()
            if hasattr(mod, 'SYNC_MONITOR_CLS')}

        for p_name, p in providers.iteritems():
            if p_name not in self.monitor_cls_for:
                self.monitor_cls_for[p_name] = self.monitor_cls_for["generic"]

        self.log = get_logger()
        self.log.bind(cpu_id=cpu_id)
        self.log.info('starting mail sync process',
                      supported_providers=module_registry.keys())

        self.syncing_accounts = set()
        self.email_sync_monitors = {}
        self.contact_sync_monitors = {}
        self.event_sync_monitors = {}
        self.poll_interval = poll_interval
        self.semaphore = BoundedSemaphore(1)

        self.stealing_enabled = config.get('SYNC_STEAL_ACCOUNTS', True)
        self.sync_hosts_for_shards = {}
        for database in config['DATABASE_HOSTS']:
            for shard in database['SHARDS']:
                # If no sync hosts are explicitly configured for the shard,
                # then try to steal from it. That way if you turn up a new
                # shard without properly allocating sync hosts to it, accounts
                # on it will still be started.
                self.sync_hosts_for_shards[shard['ID']] = shard.get(
                    'SYNC_HOSTS') or [self.host]

    def run(self):
        retry_with_logging(self._run_impl, self.log)

    @staticmethod
    def account_cpu_filter(cpu_id, total_cpus):
        return (Account.id % total_cpus == cpu_id)

    def accounts_to_start(self):
        accounts = set()
        for key in engine_manager.engines:
            try:
                with session_scope_by_shard_id(key) as db_session:
                    start_on_this_cpu = self.account_cpu_filter(
                        self.cpu_id, self.total_cpus)
                    if (self.stealing_enabled and
                            self.host in self.sync_hosts_for_shards[key]):
                        q = db_session.query(Account).filter(
                            Account.sync_host.is_(None),
                            Account.sync_should_run,
                            start_on_this_cpu)
                        unscheduled_accounts_exist = db_session.query(
                            q.exists()).scalar()
                        if unscheduled_accounts_exist:
                            # Atomically claim unscheduled syncs by setting
                            # sync_host.
                            q.update({'sync_host': self.process_identifier},
                                     synchronize_session=False)
                            db_session.commit()

                    accounts.update(id_ for id_, in
                                     db_session.query(Account.id).filter(
                                         Account.sync_should_run,
                                         Account.sync_host == self.host,
                                         start_on_this_cpu))

                    # Also start accounts for which a process identifier has
                    # been explicitly recorded, e.g. 'sync-10-77-22-22:13'.
                    # This is messy for now as we transition to this more
                    # granular scheduling method.
                    accounts.update(
                        id_ for id_, in db_session.query(Account.id).filter(
                            Account.sync_should_run,
                            Account.sync_host == self.process_identifier))

                    # Close the underlying connection rather than returning it
                    # to the pool. This allows this query to run against all
                    # shards without potentially acquiring a poorly-utilized,
                    # persistent connection from each sync host to each shard.
                    db_session.invalidate()
            except OperationalError:
                self.log.error('Database error getting accounts to start',
                               exc_info=True)
                log_uncaught_errors()
        return accounts

    def _run_impl(self):
        """
        Polls for newly registered accounts and checks for start/stop commands.

        """
        while True:
            # Determine which accounts need to be started
            start_accounts = self.accounts_to_start()
            statsd_client.gauge(
                'accounts.{}.mailsync-{}.count'.format(self.host, self.cpu_id),
                len(start_accounts))

            # Perform the appropriate action on each account
            for account_id in start_accounts:
                if account_id not in self.syncing_accounts:
                    self.start_sync(account_id)

            stop_accounts = self.syncing_accounts - set(start_accounts)
            for account_id in stop_accounts:
                self.log.info('sync service stopping sync',
                              account_id=account_id)
                self.stop_sync(account_id)
            gevent.sleep(self.poll_interval)

    def start_sync(self, account_id):
        """
        Starts a sync for the account with the given account_id.
        If that account doesn't exist, does nothing.

        """
        with self.semaphore, session_scope(account_id) as db_session:
            acc = db_session.query(Account).get(account_id)
            if acc is None:
                self.log.error('no such account', account_id=account_id)
                return
            self.log.info('starting sync', account_id=acc.id,
                          email_address=acc.email_address)

            if (acc.sync_host is not None and acc.sync_host != self.host and
                    acc.sync_host != self.process_identifier):
                self.log.error('Sync Host Mismatch',
                               message='account is syncing on another host {}'
                                       .format(acc.sync_host),
                               account_id=account_id)

            elif acc.id not in self.syncing_accounts:
                try:
                    if acc.sync_email:
                        monitor = self.monitor_cls_for[acc.provider](acc)
                        self.email_sync_monitors[acc.id] = monitor
                        monitor.start()

                    info = acc.provider_info
                    if info.get('contacts', None) and acc.sync_contacts:
                        contact_sync = ContactSync(acc.email_address,
                                                   acc.verbose_provider,
                                                   acc.id,
                                                   acc.namespace.id)
                        self.contact_sync_monitors[acc.id] = contact_sync
                        contact_sync.start()

                    if info.get('events', None) and acc.sync_events:
                        if (USE_GOOGLE_PUSH_NOTIFICATIONS and
                                acc.provider == 'gmail'):
                            event_sync = GoogleEventSync(acc.email_address,
                                                         acc.verbose_provider,
                                                         acc.id,
                                                         acc.namespace.id)
                        else:
                            event_sync = EventSync(acc.email_address,
                                                   acc.verbose_provider,
                                                   acc.id,
                                                   acc.namespace.id)
                        self.event_sync_monitors[acc.id] = event_sync
                        event_sync.start()

                    acc.sync_started()
                    self.syncing_accounts.add(acc.id)
                    db_session.add(acc)
                    db_session.commit()
                    self.log.info('Sync started', account_id=account_id,
                                  sync_host=acc.sync_host)
                except Exception:
                    self.log.error('Error starting sync', exc_info=True,
                                   account_id=account_id)
            else:
                self.log.info('sync already started', account_id=account_id)

    def stop_sync(self, account_id):
        """
        Stops the sync for the account with given account_id.
        If that account doesn't exist, does nothing.

        """

        with self.semaphore:
            # Send the shutdown command to local monitors
            self.log.info('Stopping monitors', account_id=account_id)
            if account_id in self.email_sync_monitors:
                self.email_sync_monitors[account_id].kill()
                del self.email_sync_monitors[account_id]

            # Stop contacts sync if necessary
            if account_id in self.contact_sync_monitors:
                self.contact_sync_monitors[account_id].kill()
                del self.contact_sync_monitors[account_id]

            # Stop events sync if necessary
            if account_id in self.event_sync_monitors:
                self.event_sync_monitors[account_id].kill()
                del self.event_sync_monitors[account_id]

            self.syncing_accounts.discard(account_id)

            # Update the state in the database (if necessary)
            with session_scope(account_id) as db_session:
                acc = db_session.query(Account).get(account_id)
                if acc is None:
                    self.log.error('No such account', account_id=account_id)
                    return False
                if acc.sync_host is None:
                    self.log.info('Sync not enabled', account_id=account_id)
                    return False
                if acc.sync_host != self.process_identifier:
                    self.log.error('Sync Host Mismatch',
                                   sync_host=acc.sync_host,
                                   account_id=account_id)
                    return False
                if not acc.sync_should_run:
                    clear_heartbeat_status(acc.id)
                self.log.info('sync stopped', account_id=account_id)
                acc.sync_stopped()
                db_session.commit()
                return True
