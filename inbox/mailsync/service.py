import time
import platform
import random

from gevent.lock import BoundedSemaphore
from sqlalchemy import or_, and_
from sqlalchemy.exc import OperationalError

from inbox.providers import providers
from inbox.config import config
from inbox.contacts.remote_sync import ContactSync
from inbox.events.remote_sync import EventSync, GoogleEventSync
from inbox.heartbeat.status import clear_heartbeat_status
from nylas.logging import get_logger
from nylas.logging.sentry import log_uncaught_errors
from inbox.models.session import session_scope, global_session_scope
from inbox.models import Account
from inbox.scheduling.event_queue import EventQueue, EventQueueGroup
from inbox.util.concurrency import retry_with_logging
from inbox.util.stats import statsd_client

from inbox.mailsync.backends import module_registry

USE_GOOGLE_PUSH_NOTIFICATIONS = \
    'GOOGLE_PUSH_NOTIFICATIONS' in config.get('FEATURE_FLAGS', [])

# How much time (in minutes) should all CPUs be over 90% to consider them
# overloaded.
SYNC_POLL_INTERVAL = 20
PENDING_AVGS_THRESHOLD = 10

MAX_ACCOUNTS_PER_PROCESS = config.get('MAX_ACCOUNTS_PER_PROCESS', 150)

SYNC_EVENT_QUEUE_NAME = 'sync:event_queue:{}'
SHARED_SYNC_EVENT_QUEUE_NAME = 'sync:shared_event_queue:{}'

SHARED_SYNC_EVENT_QUEUE_ZONE_MAP = {}


def shared_sync_event_queue_for_zone(zone):
    queue_name = SHARED_SYNC_EVENT_QUEUE_NAME.format(zone)
    if queue_name not in SHARED_SYNC_EVENT_QUEUE_ZONE_MAP:
        SHARED_SYNC_EVENT_QUEUE_ZONE_MAP[queue_name] = EventQueue(queue_name)
    return SHARED_SYNC_EVENT_QUEUE_ZONE_MAP[queue_name]


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
        Serves as the max timeout for the redis blocking pop.
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
        # Randomize the poll_interval so we maintain at least a little fairness
        # when using a timeout while blocking on the redis queues.
        min_poll_interval = 5
        self.poll_interval = int((random.random() * (poll_interval - min_poll_interval)) + min_poll_interval)
        self.semaphore = BoundedSemaphore(1)
        self.zone = config.get('ZONE')

        # Note that we don't partition by zone for the private queues.
        # There's not really a reason to since there's one queue per machine
        # anyways. Also, if you really want to send an Account to a mailsync
        # machine in another zone you can do so.
        self.private_queue = EventQueue(SYNC_EVENT_QUEUE_NAME.format(self.process_identifier))
        self.queue_group = EventQueueGroup([
            shared_sync_event_queue_for_zone(self.zone),
            self.private_queue,
        ])

        self.stealing_enabled = config.get('SYNC_STEAL_ACCOUNTS', True)
        self._pending_avgs_provider = None
        self.last_unloaded_account = time.time()

    def run(self):
        while True:
            retry_with_logging(self._run_impl, self.log)

    def _run_impl(self):
        """
        Waits for notifications about Account migrations and checks for start/stop commands.

        """
        # When the service first starts we should check the state of the world.
        self.poll({'queue_name': 'none'})
        event = None
        while event is None:
            event = self.queue_group.receive_event(timeout=self.poll_interval)

        if shared_sync_event_queue_for_zone(self.zone).queue_name == event['queue_name']:
            self.poll_shared_queue(event)
            return

        # We're going to re-evaluate the world so we don't need any of the
        # other pending events in our private queue.
        self._flush_private_queue()
        self.poll(event)

    def _flush_private_queue(self):
        while True:
            event = self.private_queue.receive_event(timeout=None)
            if event is None:
                break

    def poll_shared_queue(self, event):
        # Conservatively, stop accepting accounts if the process pending averages
        # is over PENDING_AVGS_THRESHOLD or if the total of accounts being
        # synced by a single process exceeds the threshold. Excessive
        # concurrency per process can result in lowered database throughput
        # or availability problems, since many transactions may be held open
        # at the same time.
        pending_avgs_over_threshold = False
        if self._pending_avgs_provider is not None:
            pending_avgs = self._pending_avgs_provider.get_pending_avgs()
            pending_avgs_over_threshold = pending_avgs[15] >= PENDING_AVGS_THRESHOLD

        if self.stealing_enabled and not pending_avgs_over_threshold and \
                len(self.syncing_accounts) < MAX_ACCOUNTS_PER_PROCESS:
            account_id = event['id']
            if self.start_sync(account_id):
                self.log.info('Claimed new unassigned account sync', account_id=account_id)
            return

        if not self.stealing_enabled:
            reason = 'stealing disabled'
        elif pending_avgs_over_threshold:
            reason = 'process pending avgs too high'
        else:
            reason = 'reached max accounts for process'
        self.log.info('Not claiming new account sync, sending event back to shared queue', reason=reason)
        shared_sync_event_queue_for_zone(self.zone).send_event(event)

    def poll(self, event):
        # Determine which accounts to sync
        start_accounts = self.account_ids_to_sync()
        statsd_client.gauge(
            'mailsync.account_counts.{}.mailsync-{}.count'.format(
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

        stop_accounts = self.account_ids_owned() - set(start_accounts)
        for account_id in stop_accounts:
            self.log.info('sync service stopping sync',
                          account_id=account_id)
            try:
                self.stop_sync(account_id)
            except OperationalError:
                self.log.error('Database error stopping account sync',
                               exc_info=True)
                log_uncaught_errors()

    def account_ids_to_sync(self):
        with global_session_scope() as db_session:
            return {r[0] for r in db_session.query(Account.id).
                filter(Account.sync_should_run,
                       or_(and_(Account.desired_sync_host == self.process_identifier,
                                Account.sync_host == None),     # noqa
                           and_(Account.desired_sync_host == None,  # noqa
                               Account.sync_host == self.process_identifier),
                           and_(Account.desired_sync_host == self.process_identifier,
                                Account.sync_host == self.process_identifier))).all()}

    def account_ids_owned(self):
        with global_session_scope() as db_session:
            return {r[0] for r in db_session.query(Account.id).
                    filter(Account.sync_host == self.process_identifier).all()}

    def register_pending_avgs_provider(self, pending_avgs_provider):
        self._pending_avgs_provider = pending_avgs_provider

    def start_sync(self, account_id):
        """
        Starts a sync for the account with the given account_id.
        If that account doesn't exist, does nothing.

        """
        with self.semaphore, session_scope(account_id) as db_session:
            acc = db_session.query(Account).with_for_update().get(account_id)
            if acc is None:
                self.log.error('no such account', account_id=account_id)
                return False
            if not acc.sync_should_run:
                return False
            if acc.desired_sync_host is not None and acc.desired_sync_host != self.process_identifier:
                return False
            if acc.sync_host is not None and acc.sync_host != self.process_identifier:
                return False
            self.log.info('starting sync', account_id=acc.id,
                          email_address=acc.email_address)

            if acc.id in self.syncing_accounts:
                self.log.info('sync already started', account_id=account_id)
                return False

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
                # TODO (mark): Uncomment this after we've transitioned to from statsd to brubeck
                # statsd_client.gauge('mailsync.sync_hosts_counts.{}'.format(acc.id), 1, delta=True)
                db_session.commit()
                self.log.info('Sync started', account_id=account_id,
                              sync_host=acc.sync_host)
            except Exception:
                self.log.error('Error starting sync', exc_info=True,
                               account_id=account_id)
                return False
        return True

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

            # Update database/heartbeat state
            with session_scope(account_id) as db_session:
                acc = db_session.query(Account).get(account_id)
                if not acc.sync_should_run:
                    clear_heartbeat_status(acc.id)
                if not acc.sync_stopped(self.process_identifier):
                    self.syncing_accounts.discard(account_id)
                    return False
                self.log.info('sync stopped', account_id=account_id)
                # TODO (mark): Uncomment this after we've transitioned to from statsd to brubeck
                # statsd_client.gauge('mailsync.sync_hosts_counts.{}'.format(acc.id), -1, delta=True)
                db_session.commit()
                self.syncing_accounts.discard(account_id)
            return True
