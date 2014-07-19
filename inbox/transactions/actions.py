"""Monitor the transaction log for changes that should be synced back to the
account backend.

TODO(emfree):
 * Track syncback failure/success state, and implement retries
   (syncback actions may be lost if the service restarts while actions are
   still pending).
 * Add better logging.
"""
import gevent
from sqlalchemy import asc, func

from inbox.util.concurrency import retry_with_logging
from inbox.log import get_logger
from inbox.models.session import session_scope
from inbox.models import ActionLog, Namespace
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

    def __init__(self, poll_interval=1, chunk_size=22, max_pool_size=22):
        self.log = get_logger()
        self.worker_pool = gevent.pool.Pool(max_pool_size)
        self.poll_interval = poll_interval
        self.chunk_size = chunk_size
        with session_scope() as db_session:
            # Just start working from the head of the log.
            # TODO(emfree): once we can do retry, persist a pointer into the
            # transaction log and advance it only on syncback success.
            self.minimum_id, = db_session.query(
                func.max(ActionLog.id)).one()
            if self.minimum_id is None:
                self.minimum_id = -1
        gevent.Greenlet.__init__(self)

    def _process_log(self):
        # TODO(emfree) handle the case that message/thread objects may have
        # been deleted in the interim
        with session_scope() as db_session:
            query = db_session.query(ActionLog). \
                filter(ActionLog.id > self.minimum_id). \
                order_by(asc(ActionLog.id)).yield_per(self.chunk_size)

            for log_entry in query:
                self.minimum_id = log_entry.id
                action_function = ACTION_FUNCTION_MAP[log_entry.action]
                namespace = db_session.query(Namespace). \
                    get(log_entry.namespace_id)
                self._execute_async_action(action_function,
                                           namespace.account_id,
                                           log_entry.record_id)

    def _execute_async_action(self, func, *args):
        self.log.info('Scheduling syncback action', func=func, args=args)
        g = gevent.Greenlet(retry_with_logging, lambda: func(*args),
                            logger=self.log)
        g.link_value(lambda _: self.log.info('Syncback action completed',
                                             func=func, args=args))
        self.worker_pool.start(g)

    def _run_impl(self):
        self.log.info('Starting action service')
        while True:
            self._process_log()
            gevent.sleep(self.poll_interval)

    def _run(self):
        retry_with_logging(self._run_impl, self.log)
