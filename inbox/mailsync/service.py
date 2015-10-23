import platform

import gevent
from setproctitle import setproctitle

from inbox.providers import providers
from inbox.config import config
from inbox.contacts.remote_sync import ContactSync
from inbox.events.remote_sync import EventSync, GoogleEventSync
from nylas.logging import get_logger
from inbox.ignition import engine_manager
from inbox.models.session import session_scope, session_scope_by_shard_id
from inbox.models import Account
from inbox.util.concurrency import retry_with_logging
from inbox.util.rdb import break_to_interpreter

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
    def __init__(self, cpu_id, total_cpus, poll_interval=10):
        self.keep_running = True
        self.host = platform.node()
        self.cpu_id = cpu_id
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

    def run(self):
        if config.get('DEBUG_CONSOLE_ON'):
            # Enable the debugging console if this flag is set. Connect to
            # localhost on the port shown in the logs to get access to a REPL
            port = None
            start_port = config.get('DEBUG_START_PORT')
            if start_port:
                port = start_port + self.cpu_id

            gevent.spawn(break_to_interpreter, port=port)

        setproctitle('inbox-sync-{}'.format(self.cpu_id))
        retry_with_logging(self._run_impl, self.log)

    def stop(self):
        for k, v in self.email_sync_monitors.iteritems():
            gevent.kill(v)
        self.keep_running = False

    @staticmethod
    def account_cpu_filter(cpu_id, total_cpus):
        return (Account.id % total_cpus == cpu_id)

    def accounts_to_start(self):
        accounts = []
        for key in engine_manager.engines:
            with session_scope_by_shard_id(key) as db_session:
                start_on_this_cpu = self.account_cpu_filter(self.cpu_id,
                                                            self.total_cpus)
                if config.get('SYNC_STEAL_ACCOUNTS', True):
                    q = db_session.query(Account).filter(
                        Account.sync_host.is_(None),
                        Account.sync_should_run,
                        start_on_this_cpu)
                    unscheduled_accounts_exist = db_session.query(
                        q.exists()).scalar()
                    if unscheduled_accounts_exist:
                        # Atomically claim unscheduled syncs by setting
                        # sync_host.
                        q.update({'sync_host': self.host},
                                 synchronize_session=False)
                        db_session.commit()

                accounts.extend([id_ for id_, in
                                 db_session.query(Account.id).filter(
                                     Account.sync_should_run,
                                     Account.sync_host == self.host,
                                     start_on_this_cpu)])
        return accounts

    def _run_impl(self):
        """
        Polls for newly registered accounts and checks for start/stop commands.

        """
        while self.keep_running:
            # Determine which accounts need to be started
            start_accounts = self.accounts_to_start()

            # Perform the appropriate action on each account
            for account_id in start_accounts:
                if account_id not in self.syncing_accounts:
                    self.start_sync(account_id)
                # If the account's sync was killed due to an exception, its
                # monitor sticks around; to restart, manually stop and start it

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
        with session_scope(account_id) as db_session:
            acc = db_session.query(Account).get(account_id)
            if acc is None:
                self.log.error('no such account', account_id=account_id)
                return
            fqdn = platform.node()
            self.log.info('starting sync', account_id=acc.id,
                          email_address=acc.email_address)

            if acc.sync_host is not None and acc.sync_host != fqdn:
                self.log.error('Sync Host Mismatch',
                               message='account is syncing on another host {}'
                                       .format(acc.sync_host),
                               account_id=account_id)

            elif acc.id not in self.syncing_accounts:
                try:
                    if acc.is_sync_locked and acc.is_killed:
                        acc.sync_unlock()
                    acc.sync_lock()

                    if acc.sync_email:
                        monitor = self.monitor_cls_for[acc.provider](acc)
                        self.email_sync_monitors[acc.id] = monitor
                        monitor.start()

                    info = acc.provider_info
                    if info.get('contacts', None) and acc.sync_contacts:
                        contact_sync = ContactSync(acc.email_address,
                                                   acc.provider,
                                                   acc.id,
                                                   acc.namespace.id)
                        self.contact_sync_monitors[acc.id] = contact_sync
                        contact_sync.start()

                    if info.get('events', None) and acc.sync_events:
                        if (USE_GOOGLE_PUSH_NOTIFICATIONS and
                                acc.provider == 'gmail'):
                            event_sync = GoogleEventSync(acc.email_address,
                                                         acc.provider,
                                                         acc.id,
                                                         acc.namespace.id)
                        else:
                            event_sync = EventSync(acc.email_address,
                                                   acc.provider,
                                                   acc.id,
                                                   acc.namespace.id)
                        self.event_sync_monitors[acc.id] = event_sync
                        event_sync.start()

                    acc.sync_started()
                    self.syncing_accounts.add(acc.id)
                    db_session.add(acc)
                    db_session.commit()
                    self.log.info('Sync started', account_id=account_id,
                                  sync_host=fqdn)
                except Exception as e:
                    self.log.error('sync_error', message=str(e.message),
                                   account_id=account_id)
            else:
                self.log.info('sync already started', account_id=account_id)

    def stop_sync(self, account_id):
        """
        Stops the sync for the account with given account_id.
        If that account doesn't exist, does nothing.

        """

        # Send the shutdown command to local monitors
        self.log.info('Stopping monitors', account_id=account_id)

        # XXX Can processing this command fail in some way?
        if account_id in self.email_sync_monitors:
            self.email_sync_monitors[account_id].shutdown.set()
            del self.email_sync_monitors[account_id]

        # Stop contacts sync if necessary
        if account_id in self.contact_sync_monitors:
            self.contact_sync_monitors[account_id].shutdown.set()
            del self.contact_sync_monitors[account_id]

        # Stop events sync if necessary
        if account_id in self.event_sync_monitors:
            self.event_sync_monitors[account_id].shutdown.set()
            del self.event_sync_monitors[account_id]

        self.syncing_accounts.remove(account_id)

        fqdn = platform.node()

        # Update the state in the database (if necessary)
        with session_scope(account_id) as db_session:
            acc = db_session.query(Account).get(account_id)
            if acc is None:
                self.log.error('No such account', account_id=account_id)
            elif acc.sync_host is None:
                self.log.info('Sync not enabled', account_id=account_id)
            elif acc.sync_host != fqdn:
                self.log.error('Sync Host Mismatch',
                               message='acct.sync_host ({}) != FQDN ({})'
                                       .format(acc.sync_host, fqdn),
                               account_id=account_id)
            else:
                self.log.info('sync stopped', account_id=account_id)
                if acc.is_sync_locked:
                    acc.sync_unlock()
                acc.sync_stopped()
                db_session.commit()
