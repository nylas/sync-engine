"""Monitor the transaction log for changes that should be synced back to the
account backend.

TODO(emfree):
 * Make this more robust across multiple machines. If you started two instances
   talking to the same database backend things could go really badly.
"""
from collections import defaultdict
from datetime import datetime
import platform
import gevent
from gevent.coros import BoundedSemaphore
from sqlalchemy.orm import contains_eager

from inbox.util.concurrency import retry_with_logging, log_uncaught_errors
from inbox.log import get_logger
logger = get_logger()
from inbox.models.session import session_scope
from inbox.models import ActionLog, Namespace, Account
from inbox.util.file import Lock
from inbox.actions.base import (mark_read, mark_unread, archive, unarchive,
                                star, unstar, save_draft, delete_draft,
                                mark_spam, unmark_spam, mark_trash,
                                unmark_trash, save_sent_email)
from inbox.events.actions.base import (create_event, delete_event,
                                       update_event)

# Global lock to ensure that only one instance of the syncback service is
# running at once. Otherwise different instances might execute the same action
# twice.
syncback_lock = Lock('/var/lock/inbox_syncback/global.lock', block=True)


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
    'save_draft': save_draft,
    'delete_draft': delete_draft,
    'save_sent_email': save_sent_email,
    'create_event': create_event,
    'delete_event': delete_event,
    'update_event': update_event,
}


ACTION_MAX_NR_OF_RETRIES = 20


class SyncbackService(gevent.Greenlet):
    """Asynchronously consumes the action log and executes syncback actions."""

    def __init__(self, poll_interval=1, retry_interval=30):
        self.log = logger.new(component='syncback')
        self.keep_running = True
        self.poll_interval = poll_interval
        self.retry_interval = retry_interval
        self.workers = gevent.pool.Group()
        # Dictionary account_id -> semaphore to serialize action syncback for
        # any particular account.
        # TODO(emfree): We really only need to serialize actions that operate
        # on any given object. But IMAP actions are already effectively
        # serialized by using an IMAP connection pool of size 1, so it doesn't
        # matter too much.
        self.account_semaphores = defaultdict(lambda: BoundedSemaphore(1))
        gevent.Greenlet.__init__(self)

    def _process_log(self):
        with session_scope() as db_session:
            # Only actions on accounts associated with this sync-engine
            query = db_session.query(ActionLog). \
                join(Namespace).join(Account). \
                filter(ActionLog.status == 'pending',
                       Account.sync_host == platform.node()). \
                order_by(ActionLog.id). \
                options(contains_eager(ActionLog.namespace, Namespace.account))

            running_action_ids = [worker.action_log_id for worker in
                                  self.workers]
            if running_action_ids:
                query = query.filter(~ActionLog.id.in_(running_action_ids))
            for log_entry in query:
                namespace = log_entry.namespace
                self.log.info('delegating action',
                              action_id=log_entry.id,
                              msg=log_entry.action)
                semaphore = self.account_semaphores[namespace.account_id]
                worker = SyncbackWorker(action_name=log_entry.action,
                                        semaphore=semaphore,
                                        action_log_id=log_entry.id,
                                        record_id=log_entry.record_id,
                                        account_id=namespace.account_id,
                                        retry_interval=self.retry_interval,
                                        extra_args=log_entry.extra_args)
                self.workers.add(worker)
                worker.start()

    def _run_impl(self):
        syncback_lock.acquire()
        self.log.info('Starting action service')
        while self.keep_running:
            self._process_log()
            gevent.sleep(self.poll_interval)

    def stop(self):
        syncback_lock.release()
        self.keep_running = False

    def _run(self):
        retry_with_logging(self._run_impl, self.log)


class SyncbackWorker(gevent.Greenlet):
    """ Worker greenlet responsible for executing a single syncback action.
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
                 account_id, retry_interval=30, extra_args=None):
        self.action_name = action_name
        self.semaphore = semaphore
        self.func = ACTION_FUNCTION_MAP[action_name]
        self.action_log_id = action_log_id
        self.record_id = record_id
        self.account_id = account_id
        self.extra_args = extra_args
        self.retry_interval = retry_interval
        gevent.Greenlet.__init__(self)

    def _run(self):
        with self.semaphore:
            log = logger.new(
                record_id=self.record_id, action_log_id=self.action_log_id,
                action=self.action_name, account_id=self.account_id,
                extra_args=self.extra_args)

            for _ in range(ACTION_MAX_NR_OF_RETRIES):
                with session_scope() as db_session:
                    try:
                        action_log_entry = db_session.query(ActionLog).get(
                            self.action_log_id)
                        if self.extra_args:
                            self.func(self.account_id, self.record_id,
                                      db_session, self.extra_args)
                        else:
                            self.func(self.account_id, self.record_id,
                                      db_session)
                        action_log_entry.status = 'successful'
                        db_session.commit()
                        latency = round((datetime.utcnow() -
                                         action_log_entry.created_at).
                                        total_seconds(), 2)
                        log.info('syncback action completed',
                                 action_id=self.action_log_id,
                                 latency=latency)
                        return

                    except Exception:
                        log_uncaught_errors(log, account_id=self.account_id)
                        with session_scope() as db_session:
                            action_log_entry.retries += 1
                            if (action_log_entry.retries ==
                                    ACTION_MAX_NR_OF_RETRIES):
                                log.critical('Max retries reached, giving up.',
                                             exc_info=True)
                                action_log_entry.status = 'failed'
                            db_session.commit()

                # Wait before retrying
                gevent.sleep(self.retry_interval)
