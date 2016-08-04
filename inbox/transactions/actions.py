"""
Monitor the action log for changes that should be synced back to the remote
backend.

TODO(emfree):
* Make this more robust across multiple machines. If you started two instances
talking to the same database backend things could go really badly.

"""
from collections import defaultdict
from datetime import datetime

import gevent
from gevent.event import Event
from gevent.queue import Queue
import random
from gevent.coros import BoundedSemaphore
import weakref

from nylas.logging import get_logger
from nylas.logging.sentry import log_uncaught_errors
logger = get_logger()
from inbox.crispin import writable_connection_pool
from inbox.ignition import engine_manager
from inbox.util.concurrency import retry_with_logging
from inbox.models.session import session_scope, session_scope_by_shard_id
from inbox.models import ActionLog
from inbox.util.misc import DummyContextManager
from inbox.util.stats import statsd_client
from inbox.actions.base import (mark_unread,
                                mark_starred,
                                move,
                                change_labels,
                                save_draft,
                                update_draft,
                                delete_draft,
                                save_sent_email,
                                create_folder,
                                create_label,
                                update_folder,
                                update_label,
                                delete_folder,
                                delete_label,
                                delete_sent_email)
from inbox.events.actions.base import (create_event, delete_event,
                                       update_event)
from inbox.config import config

MAIL_ACTION_FUNCTION_MAP = {
    'mark_unread': mark_unread,
    'mark_starred': mark_starred,
    'move': move,
    'change_labels': change_labels,
    'save_draft': save_draft,
    'update_draft': update_draft,
    'delete_draft': delete_draft,
    'save_sent_email': save_sent_email,
    'delete_sent_email': delete_sent_email,
    'create_folder': create_folder,
    'create_label': create_label,
    'update_folder': update_folder,
    'delete_folder': delete_folder,
    'update_label': update_label,
    'delete_label': delete_label,
}

EVENT_ACTION_FUNCTION_MAP = {
    'create_event': create_event,
    'delete_event': delete_event,
    'update_event': update_event,
}


def action_uses_crispin_client(action):
    return action in MAIL_ACTION_FUNCTION_MAP


def function_for_action(action):
    if action in MAIL_ACTION_FUNCTION_MAP:
        return MAIL_ACTION_FUNCTION_MAP[action]
    return EVENT_ACTION_FUNCTION_MAP[action]


ACTION_MAX_NR_OF_RETRIES = 20
NUM_PARALLEL_ACCOUNTS = 500
INVALID_ACCOUNT_GRACE_PERIOD = 60 * 60 * 2  # 2 hours


class SyncbackService(gevent.Greenlet):
    """Asynchronously consumes the action log and executes syncback actions."""

    def __init__(self, syncback_id, process_number, total_processes, poll_interval=1,
                 retry_interval=30, num_workers=NUM_PARALLEL_ACCOUNTS,
                 batch_size=10):
        self.process_number = process_number
        self.total_processes = total_processes
        self.poll_interval = poll_interval
        self.retry_interval = retry_interval
        self.batch_size = batch_size
        self.keep_running = True
        self.workers = gevent.pool.Group()
        # Dictionary account_id -> semaphore to serialize action syncback for
        # any particular account.
        # TODO(emfree): We really only need to serialize actions that operate
        # on any given object. But IMAP actions are already effectively
        # serialized by using an IMAP connection pool of size 1, so it doesn't
        # matter too much.
        self.account_semaphores = defaultdict(lambda: BoundedSemaphore(1))
        # This SyncbackService performs syncback for only and all the accounts
        # on shards it is reponsible for; shards are divided up between
        # running SyncbackServices.
        self.log = logger.new(component='syncback')
        syncback_assignments = config.get("SYNCBACK_ASSIGNMENTS", {})
        if syncback_id in syncback_assignments:
            self.keys = [key for key in engine_manager.engines
                         if key in syncback_assignments[syncback_id] and
                         key % total_processes == process_number]
        else:
            self.log.warn("No shards assigned to syncback server",
                          syncback_id=syncback_id)
            self.keys = []

        self.log = logger.new(component='syncback')
        self.num_workers = num_workers
        self.num_idle_workers = 0
        self.worker_did_finish = Event()
        self.worker_did_finish.clear()
        self.task_queue = Queue()
        self.running_action_ids = set()
        gevent.Greenlet.__init__(self)

    def _batch_log_entries(self, db_session, log_entries):
        tasks = []
        semaphore = None
        account_id = None
        for log_entry in log_entries:
            if log_entry is None:
                self.log.error('Got no action, skipping')
                continue

            if log_entry.id in self.running_action_ids:
                self.log.info('Skipping already running action',
                              action_id=log_entry.id)
                # We're already running an action for this account, so don't
                # queue up any additional actions for this account until the
                # previous batch has finished.
                return None

            namespace = log_entry.namespace
            if account_id is None:
                account_id = namespace.account.id
            else:
                assert account_id is namespace.account.id

            if namespace.account.sync_state == 'invalid':
                self.log.warning('Skipping action for invalid account',
                                 account_id=account_id,
                                 action_id=log_entry.id,
                                 action=log_entry.action)

                action_age = (datetime.utcnow() -
                              log_entry.created_at).total_seconds()

                if action_age > INVALID_ACCOUNT_GRACE_PERIOD:
                    log_entry.status = 'failed'
                    db_session.commit()
                    self.log.warning('Marking action as failed for '
                                     'invalid account, older than '
                                     'grace period',
                                     account_id=account_id,
                                     action_id=log_entry.id,
                                     action=log_entry.action)
                    statsd_client.incr('syncback.invalid_failed.total')
                    statsd_client.incr('syncback.invalid_failed.{}'.
                                       format(account_id))
                continue

            if semaphore is None:
                semaphore = self.account_semaphores[account_id]
            else:
                assert semaphore is self.account_semaphores[account_id]
            tasks.append(
                SyncbackTask(action_name=log_entry.action,
                             semaphore=semaphore,
                             action_log_id=log_entry.id,
                             record_id=log_entry.record_id,
                             account_id=account_id,
                             provider=namespace.account.
                             verbose_provider,
                             service=self,
                             retry_interval=self.retry_interval,
                             extra_args=log_entry.extra_args))
        if len(tasks) == 0:
            return None

        for task in tasks:
            self.running_action_ids.add(task.action_log_id)
            self.log.info('Syncback added task',
                          process=self.process_number,
                          action_id=task.action_log_id,
                          msg=task.action_name,
                          task_count=self.task_queue.qsize())
        return SyncbackBatchTask(semaphore, tasks, account_id)

    def _process_log(self):
        before = datetime.utcnow()
        for key in self.keys:
            with session_scope_by_shard_id(key) as db_session:

                # Get the list of namespace ids with pending actions
                namespace_ids = [ns_id[0] for ns_id in db_session.query(ActionLog.namespace_id).filter(
                    ActionLog.discriminator == 'actionlog',
                    ActionLog.status == 'pending').distinct()]

                # Pick NUM_PARALLEL_ACCOUNTS randomly to make sure we're
                # executing actions equally for each namespace_id --- we
                # don't want a single account with 100k actions hogging
                # the action log.
                namespaces_to_process = []
                if len(namespace_ids) <= NUM_PARALLEL_ACCOUNTS:
                    namespaces_to_process = namespace_ids
                else:
                    namespaces_to_process = random.sample(namespace_ids,
                                                          NUM_PARALLEL_ACCOUNTS)
                self.log.info('Syncback namespace_ids count', shard_id=key,
                              process=self.process_number,
                              num_namespace_ids=len(namespace_ids))

                for ns_id in namespaces_to_process:
                    # The discriminator filter restricts actions to IMAP. EAS
                    # uses a different system.
                    query = db_session.query(ActionLog).filter(
                        ActionLog.discriminator == 'actionlog',
                        ActionLog.status == 'pending',
                        ActionLog.namespace_id == ns_id).order_by(ActionLog.id).\
                        limit(self.batch_size)
                    task = self._batch_log_entries(db_session, query.all())
                    if task is not None:
                        self.task_queue.put(task)

        after = datetime.utcnow()
        self.log.info('Syncback completed one iteration',
                      process=self.process_number,
                      duration=(after - before).total_seconds(),
                      idle_workers=self.num_idle_workers)

    def _restart_workers(self):
        while len(self.workers) < self.num_workers:
            worker = SyncbackWorker(self)
            self.workers.add(worker)
            self.num_idle_workers += 1
            worker.start()

    def _run_impl(self):
        self.log.info('Starting syncback service',
                      process_num=self.process_number,
                      total_processes=self.total_processes,
                      keys=self.keys)
        while self.keep_running:
            self._restart_workers()
            self._process_log()
            # Wait for a worker to finish or for the fixed poll_interval,
            # whichever happens first.
            timeout = self.poll_interval
            if self.num_idle_workers == 0:
                timeout = None
            self.worker_did_finish.clear()
            self.worker_did_finish.wait(timeout=timeout)

    def stop(self):
        self.keep_running = False
        self.workers.kill()

    def _run(self):
        retry_with_logging(self._run_impl, self.log)

    def notify_worker_active(self):
        self.num_idle_workers -= 1

    def notify_worker_finished(self, action_ids):
        self.num_idle_workers += 1
        self.worker_did_finish.set()
        for action_id in action_ids:
            self.running_action_ids.remove(action_id)

    def __del__(self):
        if self.keep_running:
            self.stop()


class SyncbackBatchTask(object):

    def __init__(self, semaphore, tasks, account_id):
        self.semaphore = semaphore
        self.tasks = tasks
        self.account_id = account_id

    def _crispin_client_or_none(self):
        if self.uses_crispin_client():
            return writable_connection_pool(self.account_id).get()
        else:
            return DummyContextManager()

    def execute(self):
        log = logger.new()
        with self.semaphore:
            with self._crispin_client_or_none() as crispin_client:
                log.info("Syncback running batch of actions",
                         num_actions=len(self.tasks))
                for task in self.tasks:
                    task.crispin_client = crispin_client
                    task.execute_with_lock()

    def uses_crispin_client(self):
        return any([task.uses_crispin_client() for task in self.tasks])

    def timeout(self, per_task_timeout):
        return len(self.tasks) * per_task_timeout

    def action_log_ids(self):
        return [entry for task in self.tasks
                for entry in task.action_log_ids()]


class SyncbackTask(object):
    """
    Task responsible for executing a single syncback action. We can retry the
    action up to ACTION_MAX_NR_OF_RETRIES times before we mark it as failed.
    Note: Each task holds an account-level lock, in order to ensure that
    actions are executed in the order they were first scheduled. This means
    that in the worst case, a misbehaving action can block other actions for
    the account from executing, for up to about
    retry_interval * ACTION_MAX_NR_OF_RETRIES = 600 seconds

    TODO(emfree): Fix this with more granular locking (or a better strategy
    altogether). We only really need ordering guarantees for actions on any
    given object, not on the whole account.

    """

    def __init__(self, action_name, semaphore, action_log_id, record_id,
                 account_id, provider, service, retry_interval=30,
                 extra_args=None):
        self.parent_service = weakref.ref(service)
        self.action_name = action_name
        self.semaphore = semaphore
        self.func = function_for_action(action_name)
        self.action_log_id = action_log_id
        self.record_id = record_id
        self.account_id = account_id
        self.provider = provider
        self.extra_args = extra_args
        self.retry_interval = retry_interval
        self.crispin_client = None

    def _log_to_statsd(self, action_log_status, latency=None):
        metric_names = [
            "syncback.overall.{}".format(action_log_status),
            "syncback.providers.{}.{}".format(self.provider, action_log_status)
        ]

        for metric in metric_names:
            statsd_client.incr(metric)
            if latency:
                statsd_client.timing(metric, latency * 1000)

    def execute_with_lock(self):
        log = logger.new(
            record_id=self.record_id, action_log_id=self.action_log_id,
            action=self.action_name, account_id=self.account_id,
            extra_args=self.extra_args)

        for _ in range(ACTION_MAX_NR_OF_RETRIES):
            try:
                before_func = datetime.utcnow()
                func_args = [self.account_id, self.record_id]
                if self.extra_args:
                    func_args.append(self.extra_args)
                if self.uses_crispin_client():
                    assert self.crispin_client is not None
                    func_args.insert(0, self.crispin_client)
                self.func(*func_args)
                after_func = datetime.utcnow()

                with session_scope(self.account_id) as db_session:
                    action_log_entry = db_session.query(ActionLog).get(
                        self.action_log_id)
                    action_log_entry.status = 'successful'
                    db_session.commit()
                    latency = round((datetime.utcnow() -
                                     action_log_entry.created_at).
                                    total_seconds(), 2)
                    func_latency = round((after_func - before_func).
                                         total_seconds(), 2)
                    log.info('syncback action completed',
                             action_id=self.action_log_id,
                             latency=latency,
                             process=self.parent_service().process_number,
                             func_latency=func_latency)
                    self._log_to_statsd(action_log_entry.status, latency)
                    return
            except Exception:
                log_uncaught_errors(log, account_id=self.account_id,
                                    provider=self.provider)
                with session_scope(self.account_id) as db_session:
                    action_log_entry = db_session.query(ActionLog).get(
                        self.action_log_id)
                    action_log_entry.retries += 1
                    if (action_log_entry.retries ==
                            ACTION_MAX_NR_OF_RETRIES):
                        log.critical('Max retries reached, giving up.',
                                     exc_info=True)
                        action_log_entry.status = 'failed'
                        self._log_to_statsd(action_log_entry.status)
                        db_session.commit()
                        return
                    db_session.commit()

            # Wait before retrying
            log.info("Syncback task retrying action after sleeping",
                     duration=self.retry_interval)

            # TODO(T6974): We might want to do some kind of exponential
            # backoff with jitter to avoid the thundering herd problem if a
            # provider suddenly starts having issues for a short period of
            # time.
            gevent.sleep(self.retry_interval)

    def uses_crispin_client(self):
        return action_uses_crispin_client(self.action_name)

    def action_log_ids(self):
        return [self.action_log_id]

    def timeout(self, per_task_timeout):
        return per_task_timeout

    def execute(self):
        with self.semaphore:
            self.execute_with_lock()


class SyncbackWorker(gevent.Greenlet):

    def __init__(self, parent_service, task_timeout=60):
        self.parent_service = weakref.ref(parent_service)
        self.task_timeout = task_timeout
        gevent.Greenlet.__init__(self)

    def _run(self):
        while self.parent_service().keep_running:
            task = self.parent_service().task_queue.get()

            try:
                self.parent_service().notify_worker_active()
                gevent.with_timeout(task.timeout(self.task_timeout), task.execute)
            finally:
                self.parent_service().notify_worker_finished(
                    task.action_log_ids())
