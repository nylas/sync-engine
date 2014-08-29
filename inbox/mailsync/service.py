import platform

import gevent
from setproctitle import setproctitle

from sqlalchemy import func, or_, and_

from inbox.providers import providers, provider_info
from inbox.config import config
from inbox.contacts.remote_sync import ContactSync
from inbox.events.remote_sync import EventSync
from inbox.log import get_logger
from inbox.models.session import session_scope
from inbox.models import Account
from inbox.util.concurrency import retry_with_logging
from inbox.util.debug import attach_profiler

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
        setproctitle('inbox-sync-{}'.format(self.cpu_id))
        retry_with_logging(self._run_impl, self.log)

    def _run_impl(self):
        """
        Polls for newly registered accounts and checks for start/stop commands.

        """
        while True:
            with session_scope() as db_session:
                sync_on_this_node = or_(Account.sync_state.is_(None),
                                        Account.sync_host == platform.node())
                sync_explicitly_stopped = and_(Account.sync_state == 'stopped',
                                               Account.sync_state.isnot(None))
                start_on_this_cpu = \
                    (func.mod(Account.id, self.total_cpus) == self.cpu_id)
                start_accounts = \
                    [id_ for id_, in db_session.query(Account.id).filter(
                        sync_on_this_node,
                        ~sync_explicitly_stopped,
                        start_on_this_cpu)]
                for account_id in start_accounts:
                    if account_id not in self.monitors:
                        self.log.info('sync service starting sync',
                                      account_id=account_id)
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
                self.log.warning('account is syncing on another host',
                                 account_id=account_id,
                                 email_address=acc.email_address,
                                 sync_host=acc.sync_host)

            elif acc.id not in self.monitors:
                try:
                    if acc.is_sync_locked and acc.is_killed:
                        acc.sync_unlock()
                    acc.sync_lock()

                    monitor = self.monitor_cls_for[acc.provider](acc)
                    self.monitors[acc.id] = monitor
                    monitor.start()

                    info = provider_info(acc.provider)
                    if info.get('contacts', None):
                        contact_sync = ContactSync(acc.provider, acc.id)
                        self.contact_sync_monitors[acc.id] = contact_sync
                        contact_sync.start()

                    if info.get('events', None):
                        event_sync = EventSync(acc.provider, acc.id)
                        self.event_sync_monitors[acc.id] = event_sync
                        event_sync.start()

                    acc.start_sync(fqdn)
                    db_session.add(acc)
                    db_session.commit()
                    self.log.info('sync started', account_id=account_id)
                except Exception as e:
                    self.log.error('error encountered', msg=e.message)
            else:
                self.log.info('sync already started', account_id=account_id)

    def stop_sync(self, account_id):
        """
        Stops the sync for the account with given account_id.
        If that account doesn't exist, does nothing.

        """
        with session_scope() as db_session:
            acc = db_session.query(Account).get(account_id)
            if acc is None:
                self.log.error('no such account', account_id=account_id)
                return
            fqdn = platform.node()
            if (acc.id not in self.monitors) or \
                    (not acc.sync_enabled):
                self.log.info('sync not local', account_id=account_id)
            try:
                if acc.sync_host is None:
                    self.log.info('sync not enabled', account_id=account_id)

                assert acc.sync_host == fqdn, \
                    "sync host FQDN doesn't match: {0} <--> {1}" \
                    .format(acc.sync_host, fqdn)
                # XXX Can processing this command fail in some way?
                self.monitors[acc.id].inbox.put_nowait('shutdown')
                acc.sync_stopped()
                db_session.add(acc)
                db_session.commit()

                if acc.is_sync_locked:
                    acc.sync_unlock()

                del self.monitors[acc.id]
                # Also stop contacts sync (only relevant for Gmail
                # accounts)
                if acc.id in self.contact_sync_monitors:
                    del self.contact_sync_monitors[acc.id]
                if acc.id in self.event_sync_monitors:
                    del self.event_sync_monitors[acc.id]
                self.log.info('sync stopped', account_id=account_id)
            except Exception as e:
                self.log.error('error encountered', msg=e.message)
