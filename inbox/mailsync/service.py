import time
import platform
import collections

import gevent
from gevent.lock import BoundedSemaphore
from sqlalchemy.exc import OperationalError
import psutil

from inbox.providers import providers
from inbox.config import config
from inbox.contacts.remote_sync import ContactSync
from inbox.events.remote_sync import EventSync, GoogleEventSync
from inbox.heartbeat.status import clear_heartbeat_status
from nylas.logging import get_logger
from nylas.logging.sentry import log_uncaught_errors
from inbox.models.session import session_scope
from inbox.models import Account
from inbox.scheduling.queue import QueueClient
from inbox.util.concurrency import retry_with_logging
from inbox.util.stats import statsd_client

from inbox.mailsync.backends import module_registry

USE_GOOGLE_PUSH_NOTIFICATIONS = \
    'GOOGLE_PUSH_NOTIFICATIONS' in config.get('FEATURE_FLAGS', [])

# How much time (in minutes) should all CPUs be over 90% to consider them
# overloaded.
OVERLOAD_MIN = 20
SYNC_POLL_INTERVAL = 10
NUM_CPU_SAMPLES = (OVERLOAD_MIN * 60) / SYNC_POLL_INTERVAL
NOMINAL_THRESHOLD = 90.0

MAX_ACCOUNTS_PER_PROCESS = config.get('MAX_ACCOUNTS_PER_PROCESS', 150)


class SyncService(object):
    """
    Parameters
    ----------
    process_identifier: string
        Unique identifying string for this process (currently
        <hostname>:<process_number>)
    process_number: int
        If a system is launching 16 sync processes, value from 0-15. (Each
        sync service on the system should get a different value.)
    poll_interval : int
        Seconds between polls for account changes.
    """
    def __init__(self, process_identifier, process_number,
                 poll_interval=SYNC_POLL_INTERVAL):
        self.host = platform.node()
        self.process_number = process_number
        self.process_identifier = process_identifier
        self.monitor_cls_for = {mod.PROVIDER: getattr(
            mod, mod.SYNC_MONITOR_CLS) for mod in module_registry.values()
            if hasattr(mod, 'SYNC_MONITOR_CLS')}

        for p_name, p in providers.iteritems():
            if p_name not in self.monitor_cls_for:
                self.monitor_cls_for[p_name] = self.monitor_cls_for["generic"]

        self.log = get_logger()
        self.log.bind(process_number=process_number)
        self.log.info('starting mail sync process',
                      supported_providers=module_registry.keys())

        self.syncing_accounts = set()
        self.email_sync_monitors = {}
        self.contact_sync_monitors = {}
        self.event_sync_monitors = {}
        self.poll_interval = poll_interval
        self.semaphore = BoundedSemaphore(1)

        self.stealing_enabled = config.get('SYNC_STEAL_ACCOUNTS', True)
        self.zone = config.get('ZONE')
        self.queue_client = QueueClient(self.zone)
        self.rolling_cpu_counts = collections.deque(maxlen=NUM_CPU_SAMPLES)
        self.last_unloaded_account = time.time()

        # Fill the queue with initial values.
        null_cpu_values = [0.0 for cpu in psutil.cpu_percent(percpu=True)]
        for i in range(NUM_CPU_SAMPLES):
            self.rolling_cpu_counts.append(null_cpu_values)

    def run(self):
        retry_with_logging(self._run_impl, self.log)

    def _run_impl(self):
        """
        Polls for newly registered accounts and checks for start/stop commands.

        """
        while True:
            self.poll()
            gevent.sleep(self.poll_interval)

    def _compute_cpu_average(self):
        """
        Use our CPU data to compute the average CPU usage for this machine.
        """

        # We can just zip and sum the data because psutil always returns
        # results in the same order.
        return [sum(x) / float(NUM_CPU_SAMPLES) for x in zip(*self.rolling_cpu_counts)]

    def poll(self):
        # We really don't want to take on more load than we can bear, so we
        # need to check the CPU usage before accepting new accounts.
        # Note that we can't check this for the current core because the kernel
        # transparently moves programs across cores.
        usage_per_cpu = psutil.cpu_percent(percpu=True)
        self.rolling_cpu_counts.append(usage_per_cpu)

        cpu_averages = self._compute_cpu_average()

        cpus_over_nominal = all([cpu_usage > NOMINAL_THRESHOLD for cpu_usage in cpu_averages])

        # Conservatively, stop accepting accounts if the CPU usage is over
        # NOMINAL_THRESHOLD for every core, or if the total # of accounts
        # being synced by a single process exceeds the threshold. Excessive
        # concurrency per process can result in lowered database throughput
        # or availability problems, since many transactions may be held open
        # at the same time.
        if self.stealing_enabled and not cpus_over_nominal and \
                len(self.syncing_accounts) < MAX_ACCOUNTS_PER_PROCESS:
            r = self.queue_client.claim_next(self.process_identifier)
            if r:
                self.log.info('Claimed new account sync', account_id=r)

        # Determine which accounts to sync
        start_accounts = self.accounts_to_sync()
        statsd_client.gauge(
            'accounts.{}.mailsync-{}.count'.format(
                self.host, self.process_number), len(start_accounts))

        # Perform the appropriate action on each account
        for account_id in start_accounts:
            if account_id not in self.syncing_accounts:
                try:
                    self.start_sync(account_id)
                except OperationalError:
                    self.log.error('Database error starting account sync',
                                   exc_info=True)
                    log_uncaught_errors()

        stop_accounts = self.syncing_accounts - set(start_accounts)
        for account_id in stop_accounts:
            self.log.info('sync service stopping sync',
                          account_id=account_id)
            try:
                self.stop_sync(account_id)
            except OperationalError:
                self.log.error('Database error stopping account sync',
                               exc_info=True)
                log_uncaught_errors()

    def accounts_to_sync(self):
        return {int(k) for k, v in self.queue_client.assigned().items()
                if v == self.process_identifier}

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

            if acc.id not in self.syncing_accounts:
                try:
                    acc.sync_host = self.process_identifier
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

            # Update database/heartbeat state
            with session_scope(account_id) as db_session:
                acc = db_session.query(Account).get(account_id)
                if not acc.sync_should_run:
                    clear_heartbeat_status(acc.id)
                if acc.sync_stopped(self.process_identifier):
                    self.log.info('sync stopped', account_id=account_id)

            r = self.queue_client.unassign(account_id, self.process_identifier)
            return r
