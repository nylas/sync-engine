from gevent import Greenlet, GreenletExit, event

from nylas.logging import get_logger
log = get_logger()
from inbox.util.debug import bind_context
from inbox.util.concurrency import retry_with_logging
from inbox.models.session import session_scope

THROTTLE_COUNT = 200
THROTTLE_WAIT = 60


class MailsyncError(Exception):
    pass


class MailsyncDone(GreenletExit):
    pass


class BaseMailSyncMonitor(Greenlet):
    """
    The SYNC_MONITOR_CLS for all mail sync providers should subclass this.

    Parameters
    ----------
    account_id : int
        Which account to sync.
    email_address : str
        Email address for `account_id`.
    provider : str
        Provider for `account_id`.
    heartbeat : int
        How often to check for commands.
    """

    def __init__(self, account, heartbeat=1):
        bind_context(self, 'mailsyncmonitor', account.id)
        self.shutdown = event.Event()
        # how often to check inbox, in seconds
        self.heartbeat = heartbeat
        self.log = log.new(component='mail sync', account_id=account.id)
        self.account_id = account.id
        self.namespace_id = account.namespace.id
        self.email_address = account.email_address
        self.provider_name = account.verbose_provider

        Greenlet.__init__(self)

    def _run(self):
        try:
            return retry_with_logging(self._run_impl,
                                      account_id=self.account_id,
                                      provider=self.provider_name,
                                      logger=self.log)
        except GreenletExit:
            self._cleanup()
            raise

    def _run_impl(self):
        self.sync = Greenlet(retry_with_logging, self.sync,
                             account_id=self.account_id,
                             provider=self.provider_name,
                             logger=self.log)
        self.sync.start()
        self.sync.join()

        if self.sync.successful():
            return self._cleanup()

        self.log.error('mail sync should run forever',
                       provider=self.provider_name,
                       account_id=self.account_id,
                       exc=self.sync.exception)
        raise self.sync.exception

    def sync(self):
        raise NotImplementedError

    def _cleanup(self):
        self.sync.kill()
        with session_scope(self.namespace_id) as mailsync_db_session:
            map(lambda x: x.set_stopped(mailsync_db_session),
                self.folder_monitors)
        self.folder_monitors.kill()
