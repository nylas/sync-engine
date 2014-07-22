"""Monitor the transaction log for changes that should be synced back to the
account backend.

TODO(emfree):
 * Track syncback failure/success state, and implement retries
   (syncback actions may be lost if the service restarts while actions are
   still pending).
 * Add better logging.
"""
import gevent
from sqlalchemy import asc

from inbox.util.concurrency import retry_with_logging
from inbox.log import get_logger
from inbox.models.session import session_scope
from inbox.models import ActionLog, Namespace
from inbox.sqlalchemy_ext.util import safer_yield_per
from inbox.actions import (mark_read, mark_unread, archive, unarchive, star,
                           unstar, save_draft, delete_draft, mark_spam,
                           unmark_spam, mark_trash, unmark_trash, send_draft)

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
    'delete_draft': delete_draft
}


class SyncbackService(gevent.Greenlet):
    """Asynchronously consumes the action log and executes syncback actions."""

    def __init__(self, poll_interval=1, chunk_size=100, max_pool_size=22):
        self.log = get_logger()
        self.worker_pool = gevent.pool.Pool(max_pool_size)
        self.poll_interval = poll_interval
        self.chunk_size = chunk_size
        gevent.Greenlet.__init__(self)

    def _process_log(self):
        # TODO(emfree) handle the case that message/thread objects may have
        # been deleted in the interim.
        with session_scope() as db_session:
            query = db_session.query(ActionLog). \
                filter(ActionLog.executed == False). \
                order_by(asc(ActionLog.id))

            for log_entry in safer_yield_per(query, ActionLog.id, 0,
                                             self.chunk_size):
                action_function = ACTION_FUNCTION_MAP[log_entry.action]
                namespace = db_session.query(Namespace). \
                    get(log_entry.namespace_id)
                worker = SyncbackWorker(action_function, log_entry.id,
                                        log_entry.record_id,
                                        namespace.account_id)
                self.worker_pool.start(worker)

    def _run_impl(self):
        self.log.info('Starting action service')
        while True:
            self._process_log()
            gevent.sleep(self.poll_interval)

    def _run(self):
        retry_with_logging(self._run_impl, self.log)


class SyncbackWorker(gevent.Greenlet):
    """A greenlet spawned to execute a single syncback action."""
    def __init__(self, func, action_log_id, record_id, account_id):
        self.func = func
        self.log = get_logger()
        self.log.bind(record_id=record_id, action_log_id=action_log_id)
        self.action_log_id = action_log_id
        self.record_id = record_id
        self.account_id = account_id
        gevent.Greenlet.__init__(self)

    def _run(self):
        retry_with_logging(self._run_impl, self.log)

    def _run_impl(self):
        # Not ignoring soft-deleted objects here because if you, say, delete a
        # draft, we still need to access the object to delete it on the remote.
        with session_scope(ignore_soft_deletes=False) as db_session:
            self.func(self.account_id, self.record_id, db_session)
            action_log_entry = db_session.query(ActionLog).get(
                self.action_log_id)
            action_log_entry.executed = True
            db_session.commit()
            self.log.info('syncback action completed')
