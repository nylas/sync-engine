from gevent import event, Greenlet, sleep

from inbox.log import get_logger
logger = get_logger()

from inbox.util.concurrency import retry_and_report_killed
from inbox.heartbeat.status import HeartbeatStatusProxy, clear_heartbeat_status
from inbox.basicauth import ConnectionError, ValidationError
from inbox.models import Account
from inbox.models.session import session_scope


class BaseSyncMonitor(Greenlet):
    """
    Abstracted sync monitor, based on BaseMailSyncMonitor but not mail-specific

    Subclasses should run
    bind_context(self, 'mailsyncmonitor', account.id)


    poll_frequency : int
        How often to check for commands.
    retry_fail_classes : list
        Exceptions to *not* retry on.

    """
    def __init__(self, account_id, namespace_id, folder_id, poll_frequency=1,
                 retry_fail_classes=[]):

        self.account_id = account_id
        self.namespace_id = namespace_id
        self.poll_frequency = poll_frequency
        self.retry_fail_classes = retry_fail_classes
        self.folder_id = folder_id

        self.log = logger.new(account_id=account_id)

        self.shutdown = event.Event()
        self.heartbeat_status = HeartbeatStatusProxy(self.account_id,
                                                     self.folder_id)

        Greenlet.__init__(self)

    def _run(self):
        return retry_and_report_killed(self._run_impl,
                                       account_id=self.account_id,
                                       logger=self.log,
                                       fail_classes=self.retry_fail_classes)

    def _run_impl(self):
        # Return true/false based on whether the greenlet succeeds or throws
        # and error. Note this is not how the mailsync monitor works
        try:
            while True:
                # Check to see if this greenlet should exit
                if self.shutdown.is_set():
                    self._cleanup()
                    return False

                try:
                    self.sync()
                    self.heartbeat_status.publish(state='poll')

                # If we get a connection or API permissions error, then sleep
                # 2x poll frequency.
                except ConnectionError:
                    self.log.error('Error while polling', exc_info=True)
                    self.heartbeat_status.publish(state='poll error')
                    sleep(self.poll_frequency)
                sleep(self.poll_frequency)
        except ValidationError:
            # Bad account credentials; exit.
            self.log.error('Error while establishing the connection',
                           exc_info=True)
            self._cleanup()
            with session_scope() as db_session:
                account = db_session.query(Account).get(self.account_id)
                account.sync_state = 'invalid'

            return False

    def sync(self):
        """ Subclasses should override this to do work """
        raise NotImplementedError

    def _cleanup(self):
        clear_heartbeat_status(self.account_id, folder_id=self.folder_id)
