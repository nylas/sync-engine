"""
Monitor the action log for changes that should be synced back to the remote
backend.

"""
from datetime import datetime

from nylas.logging import get_logger
log = get_logger()
from nylas.logging.sentry import log_uncaught_errors
from inbox.models.session import session_scope
from inbox.models import ActionLog
from inbox.util.stats import statsd_client
from inbox.actions.base import (mark_unread, mark_starred, move, change_labels,
                                save_draft, update_draft, delete_draft,
                                save_sent_email, delete_sent_email,
                                create_folder, create_label, update_folder,
                                update_label, delete_folder, delete_label)
from inbox.events.actions.base import (create_event, delete_event,
                                       update_event)

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


class SyncbackHandler(object):
    def __init__(self, account_id, namespace_id, provider):
        self.account_id = account_id
        self.namespace_id = namespace_id
        self.provider = provider

    def send_client_changes(self):
        with session_scope(self.namespace_id) as db_session:
            q = db_session.query(ActionLog).filter(
                ActionLog.namespace_id == self.namespace_id,
                ActionLog.discriminator == 'actionlog',
                ActionLog.status == 'pending').\
                order_by(ActionLog.id)
            actions = q.limit(100).all()
            db_session.expunge_all()

        if not actions:
            log.info('No actions to syncback')
            return

        log.info('Performing syncback', num_actions=len(actions))

        for action in actions:
            try:
                func = ACTION_FUNCTION_MAP[action.action]
                if action.extra_args:
                    func(self.account_id, action.record_id, action.extra_args)
                else:
                    func(self.account_id, action.record_id)
                self.mark_success(action.id)
            except Exception:
                self.mark_failure(action.id)

    def mark_success(self, actionlog_id):
        with session_scope(self.account_id) as db_session:
            actionlog = db_session.query(ActionLog).get(actionlog_id)
            actionlog.status = 'successful'
            db_session.commit()

            latency = round((datetime.utcnow() -
                             actionlog.created_at).total_seconds(), 2)
            log.info('syncback action completed',
                     action_id=actionlog.id, latency=latency)
            self._log_to_statsd(actionlog.status, latency)

    def mark_failure(self, actionlog_id):
        log_uncaught_errors(log, component='syncback', account_id=self.account_id,
                            action_id=actionlog_id, provider=self.provider)

        with session_scope(self.account_id) as db_session:
            actionlog = db_session.query(ActionLog).get(actionlog_id)
            actionlog.retries += 1

            if actionlog.retries == ACTION_MAX_NR_OF_RETRIES:
                log.critical('Max retries reached, giving up.', exc_info=True)
                actionlog.status = 'failed'
                db_session.commit()

                self._log_to_statsd(actionlog.status)

    def _log_to_statsd(self, action_log_status, latency=None):
        metric_names = [
            'syncback.overall.{}'.format(action_log_status),
            'syncback.providers.{}.{}'.format(self.provider, action_log_status)
        ]

        for metric in metric_names:
            statsd_client.incr(metric)
            if latency:
                statsd_client.timing(metric, latency * 1000)
