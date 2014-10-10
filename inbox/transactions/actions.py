"""Monitor the transaction log for changes that should be synced back to the
account backend.

TODO(emfree):
 * Make this more robust across multiple machines. If you started two instances
   talking to the same database backend things could go really badly.
"""
from collections import defaultdict
import platform
import gevent
from gevent.coros import BoundedSemaphore
from sqlalchemy import asc

from inbox.util.concurrency import retry_with_logging, log_uncaught_errors
from inbox.log import get_logger
logger = get_logger()
from inbox.models.session import session_scope
from inbox.models import ActionLog, Namespace
from inbox.sqlalchemy_ext.util import safer_yield_per
from inbox.util.file import Lock
from inbox.util.misc import ProviderSpecificException
from inbox.actions import (mark_read, mark_unread, archive, unarchive, star,
                           unstar, save_draft, delete_draft, mark_spam,
                           unmark_spam, mark_trash, unmark_trash, send_draft,
                           send_directly)

# Global lock to ensure that only one instance of the syncback service is
# running at once. Otherwise different instances might execute the same action
# twice.
syncback_lock = Lock('/var/lock/inbox_syncback/global.lock', block=False)

ACTION_FUNCTION_MAP = {
    'archive': archive,
    'unarchive': unarchive,
    'mark_read': mark_read,
    'mark_unread': mark_unread,
    'star': star,
    'unstar': unstar,
    'mark_spam': mark_spam,
    'unmark_spam': unmark_spam,
    'mark_trash': mark_trash,
    'unmark_trash': unmark_trash,
    'send_draft': send_draft,
    'save_draft': save_draft,
    'delete_draft': delete_draft,
    'send_directly': send_directly
}


CONCURRENCY_LIMIT = 3
ACTION_MAX_NR_OF_RETRIES = 20


class SyncbackService(gevent.Greenlet):
    """Asynchronously consumes the action log and executes syncback actions."""

    def __init__(self, poll_interval=1, chunk_size=100):
        semaphore_factory = lambda: BoundedSemaphore(CONCURRENCY_LIMIT)
        self.semaphore_map = defaultdict(semaphore_factory)
        self.keep_running = True
        self.running = False
        self.log = logger.new(component='syncback')
        self.poll_interval = poll_interval
        self.chunk_size = chunk_size
        self._scheduled_actions = set()
        gevent.Greenlet.__init__(self)

    def _process_log(self):
        # TODO(emfree) handle the case that message/thread objects may have
        # been deleted in the interim.
        with session_scope() as db_session:
            query = db_session.query(ActionLog).filter(
                ActionLog.status == 'pending',
                ActionLog.retries < ACTION_MAX_NR_OF_RETRIES)

            if self._scheduled_actions:
                query = query.filter(
                    ~ActionLog.id.in_(self._scheduled_actions))
            query = query.order_by(asc(ActionLog.id))

            for log_entry in safer_yield_per(query, ActionLog.id, 0,
                                             self.chunk_size):
                action_function = ACTION_FUNCTION_MAP[log_entry.action]
                namespace = db_session.query(Namespace). \
                    get(log_entry.namespace_id)

                # Only actions on accounts associated with this sync-engine
                if namespace.account.sync_host != platform.node():
                    continue

                self._scheduled_actions.add(log_entry.id)
                self.log.info('delegating action',
                              action_id=log_entry.id,
                              msg=log_entry.action)
                semaphore = self.semaphore_map[(namespace.account_id,
                                                log_entry.action)]
                gevent.spawn(syncback_worker, semaphore, action_function,
                             log_entry.id, log_entry.record_id,
                             namespace.account_id, syncback_service=self,
                             extra_args=log_entry.extra_args)

    def remove_from_schedule(self, log_entry_id):
        self._scheduled_actions.discard(log_entry_id)

    def _acquire_lock_nb(self):
        """Spin on the global syncback lock."""
        while self.keep_running:
            try:
                syncback_lock.acquire()
                return
            except IOError:
                gevent.sleep()

    def _release_lock_nb(self):
        syncback_lock.release()

    def _run_impl(self):
        self.running = True
        self._acquire_lock_nb()
        self.log.info('Starting action service')
        while self.keep_running:
            self._process_log()
            gevent.sleep(self.poll_interval)
        self._release_lock_nb()
        self.running = False

    def _run(self):
        retry_with_logging(self._run_impl, self.log)

    def stop(self):
        # Wait for main thread to stop running
        self.keep_running = False
        while self.running:
            gevent.sleep()


def syncback_worker(semaphore, func, action_log_id, record_id, account_id,
                    syncback_service, retry_interval=30, extra_args=None):
        with semaphore:
            log = logger.new(record_id=record_id, action_log_id=action_log_id,
                             action=func, account_id=account_id,
                             extra_args=extra_args)
            # Not ignoring soft-deleted objects here because if you, say,
            # delete a draft, we still need to access the object to delete it
            # on the remote.
            try:
                with session_scope(ignore_soft_deletes=False) as db_session:
                    if extra_args:
                        func(account_id, record_id, db_session, extra_args)
                    else:
                        func(account_id, record_id, db_session)
                    action_log_entry = db_session.query(ActionLog).get(
                        action_log_id)
                    action_log_entry.status = 'successful'
                    db_session.commit()
                    log.info('syncback action completed',
                             action_id=action_log_id)
                    syncback_service.remove_from_schedule(action_log_id)
            except Exception as e:
                # To reduce error-reporting noise, don't ship to Sentry
                # if not actionable.
                if isinstance(e, ProviderSpecificException):
                    log.warning('Uncaught error', exc_info=True)
                else:
                    log_uncaught_errors(log, account_id=account_id)

                action_log_entry = db_session.query(ActionLog).get(
                        action_log_id)
                action_log_entry.retries += 1

                if action_log_entry.retries == ACTION_MAX_NR_OF_RETRIES:
                    log.error('Max retries reached, giving up.',
                              action_id=action_log_id, account_id=account_id)
                    action_log_entry.status = 'failed'

                db_session.commit()

                # Wait for a bit before retrying
                gevent.sleep(retry_interval)

                # Remove the entry from the scheduled set so that it can be
                # retried or given up on.
                syncback_service.remove_from_schedule(action_log_id)

                # Again, don't raise on exceptions that require
                # provider-specific handling e.g. EAS
                if not isinstance(e, ProviderSpecificException):
                    raise
