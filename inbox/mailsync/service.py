import platform

import gevent
from setproctitle import setproctitle

from sqlalchemy import func, or_, and_

from inbox.providers import providers
from inbox.config import config
from inbox.contacts.remote_sync import ContactSync
from inbox.events.remote_sync import EventSync
from inbox.log import get_logger
from inbox.models.session import session_scope
from inbox.models import Account
from inbox.util.concurrency import retry_with_logging
from inbox.util.debug import attach_profiler
from inbox.util.rdb import break_to_interpreter

from inbox.mailsync.backends import module_registry


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
    def __init__(self, cpu_id, total_cpus, poll_interval=1):
        self.keep_running = True
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

        self.monitors = {}
        self.contact_sync_monitors = {}
        self.event_sync_monitors = {}
        self.poll_interval = poll_interval

    def run(self):
        if config.get('DEBUG_PROFILING_ON'):
            # If config flag is set, get live top-level profiling output on
            # stdout by doing kill -SIGTRAP <sync_process>.
            # This slows things down so you probably don't want to do it
            # normally.
            attach_profiler()

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
        for k, v in self.monitors.iteritems():
            gevent.kill(v)
        self.keep_running = False

    def _get_local_accounts(self):
        with session_scope() as db_session:
            # Whether this node should use a work-stealing style approach
            # to claiming accounts that don't have a specified sync_host
            steal = and_(Account.sync_host.is_(None),
                         config.get('SYNC_STEAL_ACCOUNTS', True))

            # Whether accounts should be claimed via explicis scheduling
            explicit = Account.sync_host == platform.node()

            # Start new syncs on this node if the sync_host is set
            # explicitly to this node, or if the sync_host is not set and
            # this node is configured to use a work-stealing style approach
            # to scheduling accounts.
            start = and_(Account.sync_state.is_(None),
                         or_(steal, explicit))

            # Don't restart a previous sync if it's sync_host is not
            # this node (i.e. it's running elsewhere),
            # was explicitly stopped or
            # killed due to invalid credentials
            dont_start = or_(Account.sync_host != platform.node(),
                             Account.sync_state.in_(['stopped',
                                                     'invalid']))

            # Start IFF an account IS in the set of startable syncs OR
            # NOT in the set of dont_start syncs
            sync_on_this_node = or_(start, ~dont_start)

            start_on_this_cpu = \
                (func.mod(Account.id, self.total_cpus) == self.cpu_id)

            start_accounts = \
                [id_ for id_, in db_session.query(Account.id).filter(
                    sync_on_this_node,
                    start_on_this_cpu)]

            return start_accounts

    def _run_impl(self):
        """
        Polls for newly registered accounts and checks for start/stop commands.

        """
        while self.keep_running:
            # Determine which accounts need to be started
            start_accounts = self._get_local_accounts()

            # Perform the appropriate action on each account
            for account_id in start_accounts:
                if account_id not in self.monitors:
                    self.start_sync(account_id)

            stop_accounts = set(self.monitors.keys()) - \
                set(start_accounts)
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
        with session_scope() as db_session:
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

            elif acc.id not in self.monitors:
                try:
                    if acc.is_sync_locked and acc.is_killed:
                        acc.sync_unlock()
                    acc.sync_lock()

                    monitor = self.monitor_cls_for[acc.provider](acc)
                    self.monitors[acc.id] = monitor
                    monitor.start()

                    info = acc.provider_info
                    if info.get('contacts', None) and acc.sync_contacts:
                        contact_sync = ContactSync(acc.provider, acc.id,
                                                   acc.namespace.id)
                        self.contact_sync_monitors[acc.id] = contact_sync
                        contact_sync.start()

                    if info.get('events', None) and acc.sync_events:
                        event_sync = EventSync(acc.provider, acc.id,
                                               acc.namespace.id)
                        self.event_sync_monitors[acc.id] = event_sync
                        event_sync.start()

                    acc.start_sync(fqdn)
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
        self.monitors[account_id].shutdown.set()
        del self.monitors[account_id]

        # Stop contacts sync if necessary
        if account_id in self.contact_sync_monitors:
            self.contact_sync_monitors[account_id].shutdown.set()
            del self.contact_sync_monitors[account_id]

        # Stop events sync if necessary
        if account_id in self.event_sync_monitors:
            self.event_sync_monitors[account_id].shutdown.set()
            del self.event_sync_monitors[account_id]

        fqdn = platform.node()

        # Update the state in the database (if necessary)
        with session_scope() as db_session:
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
