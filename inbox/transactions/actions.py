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
import random
from gevent.coros import BoundedSemaphore

from nylas.logging import get_logger
from nylas.logging.sentry import log_uncaught_errors
logger = get_logger()
from inbox.ignition import engine_manager
from inbox.util.concurrency import retry_with_logging
from inbox.models.session import session_scope, session_scope_by_shard_id
from inbox.models import ActionLog
from inbox.util.stats import statsd_client
from inbox.actions.base import (mark_unread, mark_starred, move, change_labels,
                                save_draft, update_draft, delete_draft,
                                save_sent_email, create_folder, create_label,
                                update_folder, update_label, delete_folder,
                                delete_label, delete_sent_email)
from inbox.events.actions.base import (create_event, delete_event,
                                       update_event)
from inbox.config import config

ACTION_FUNCTION_MAP = {
    'mark_unread': mark_unread,
    'mark_starred': mark_starred,
    'move': move,
    'change_labels': change_labels,
    'save_draft': save_draft,
    'update_draft': update_draft,
    'delete_draft': delete_draft,
    'save_sent_email': save_sent_email,
    'delete_sent_email': delete_sent_email,
    'create_event': create_event,
    'delete_event': delete_event,
    'update_event': update_event,
    'create_folder': create_folder,
    'create_label': create_label,
    'update_folder': update_folder,
    'delete_folder': delete_folder,
    'update_label': update_label,
    'delete_label': delete_label
}


ACTION_MAX_NR_OF_RETRIES = 20
NUM_PARALLEL_ACCOUNTS = 500
INVALID_ACCOUNT_GRACE_PERIOD = 60 * 60 * 2  # 2 hours


class SyncbackService(gevent.Greenlet):
    """Asynchronously consumes the action log and executes syncback actions."""

    def __init__(self, syncback_id, process_number, total_processes, poll_interval=1,
                 retry_interval=30):
        self.process_number = process_number
        self.total_processes = total_processes
        self.poll_interval = poll_interval
        self.retry_interval = retry_interval
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
        gevent.Greenlet.__init__(self)

    def _process_log(self):
        before = datetime.utcnow()
        for key in self.keys:
            with session_scope_by_shard_id(key) as db_session:

                # Get the list of namespace ids with pending actions
                namespace_ids = [ns_id[0] for ns_id in db_session.query(ActionLog.namespace_id).filter(
                    ActionLog.discriminator == 'actionlog',
                    ActionLog.status == 'pending').distinct()]

                running_action_ids = {worker.action_log_id for worker in
                                      self.workers}

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
                        limit(1)

                    log_entry = query.first()

                    if log_entry is None:
                        self.log.error('Got a non-existing action, skipping')
                        continue

                    if log_entry.id in running_action_ids:
                        self.log.info('Skipping already running action',
                                      action_id=log_entry.id)
                        continue

                    namespace = log_entry.namespace
                    if namespace.account.sync_state == 'invalid':
                        self.log.warning('Skipping action for invalid account',
                                         account_id=namespace.account.id,
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
                                             account_id=namespace.account.id,
                                             action_id=log_entry.id,
                                             action=log_entry.action)
                            statsd_client.incr('syncback.invalid_failed.total')
                            statsd_client.incr('syncback.invalid_failed.{}'.
                                               format(namespace.account.id))
                        continue

                    self.log.info('delegating action',
                                  action_id=log_entry.id,
                                  msg=log_entry.action)

                    semaphore = self.account_semaphores[namespace.account_id]
                    worker = SyncbackWorker(action_name=log_entry.action,
                                            semaphore=semaphore,
                                            action_log_id=log_entry.id,
                                            record_id=log_entry.record_id,
                                            account_id=namespace.account_id,
                                            provider=namespace.account.
                                            verbose_provider,
                                            service=self,
                                            retry_interval=self.retry_interval,
                                            extra_args=log_entry.extra_args)
                    self.workers.add(worker)
                    self.log.info('Syncback added worker',
                                  process=self.process_number,
                                  worker_count=len(self.workers))
                    worker.start()
        after = datetime.utcnow()
        self.log.info('Syncback completed one iteration',
                      process=self.process_number,
                      duration=(after - before).total_seconds())

    def _run_impl(self):
        self.log.info('Starting syncback service',
                      process_num=self.process_number,
                      total_processes=self.total_processes,
                      keys=self.keys)
        while self.keep_running:
            self._process_log()
            # TODO(T6973): Don't wait to poll if we know we have more actions
            # that need processing.
            gevent.sleep(self.poll_interval)

    def stop(self):
        self.workers.kill()
        self.keep_running = False

    def _run(self):
        retry_with_logging(self._run_impl, self.log)


class SyncbackWorker(gevent.Greenlet):
    """
    Worker greenlet responsible for executing a single syncback action.
    The worker can retry the action up to ACTION_MAX_NR_OF_RETRIES times
    before marking it as failed.
    Note: Each worker holds an account-level lock, in order to ensure that
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
        self.parent_service = service
        self.action_name = action_name
        self.semaphore = semaphore
        self.func = ACTION_FUNCTION_MAP[action_name]
        self.action_log_id = action_log_id
        self.record_id = record_id
        self.account_id = account_id
        self.provider = provider
        self.extra_args = extra_args
        self.retry_interval = retry_interval
        gevent.Greenlet.__init__(self)

    def _log_to_statsd(self, action_log_status, latency=None):
        metric_names = [
            "syncback.overall.{}".format(action_log_status),
            "syncback.providers.{}.{}".format(self.provider, action_log_status)
        ]

        for metric in metric_names:
            statsd_client.incr(metric)
            if latency:
                statsd_client.timing(metric, latency * 1000)

    def _run(self):
        with self.semaphore:
            log = logger.new(
                record_id=self.record_id, action_log_id=self.action_log_id,
                action=self.action_name, account_id=self.account_id,
                extra_args=self.extra_args)

            for _ in range(ACTION_MAX_NR_OF_RETRIES):
                try:
                    before_func = datetime.utcnow()
                    if self.extra_args:
                        self.func(self.account_id, self.record_id,
                                  self.extra_args)
                    else:
                        self.func(self.account_id, self.record_id)
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
                                 process=self.parent_service.process_number,
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
                log.info("Syncback worker retrying action after sleeping",
                         duration=self.retry_interval)

                # TODO(T6974): We might want to do some kind of exponential
                # backoff with jitter to avoid the thundering herd problem if a
                # provider suddenly starts having issues for a short period of
                # time.
                gevent.sleep(self.retry_interval)
