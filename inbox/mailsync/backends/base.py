from gevent import Greenlet, joinall, sleep, GreenletExit, event

from nylas.logging import get_logger
log = get_logger()
from inbox.util.debug import bind_context
from inbox.util.concurrency import retry_with_logging
from inbox.util.itert import partition
from inbox.models.session import session_scope
from inbox.mailsync.exc import SyncException
from inbox.heartbeat.status import clear_heartbeat_status

THROTTLE_COUNT = 200
THROTTLE_WAIT = 60


class MailsyncError(Exception):
    pass


class MailsyncDone(GreenletExit):
    pass


def gevent_check_join(log, threads, errmsg):
    """
    Block until all threads have completed and throw an error if threads
    are not successful.

    """
    joinall(threads)
    errors = [thread.exception for thread in threads
              if not thread.successful()]
    if errors:
        log.error(errmsg)
        for error in errors:
            log.error(error)
        raise SyncException("Fatal error encountered")


def new_or_updated(uids, local_uids):
    """
    HIGHESTMODSEQ queries return a list of messages that are *either*
    new *or* updated. We do different things with each, so we need to
    sort out which is which.

    """
    return partition(lambda x: x in local_uids, uids)


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
        return retry_with_logging(self._run_impl, account_id=self.account_id,
                                  provider=self.provider_name, logger=self.log)

    def _run_impl(self):
        sync = Greenlet(retry_with_logging, self.sync,
                        account_id=self.account_id,
                        provider=self.provider_name,
                        logger=self.log)
        sync.start()

        while not sync.ready():
            if self.shutdown.is_set():
                # Ctrl-c, basically!
                self.log.info('Stopping sync', email=self.email_address,
                              account_id=self.account_id)
                # Make sure the parent can't start/stop any folder monitors
                # first
                sync.kill(block=True)

                return self._cleanup()
            else:
                sleep(self.heartbeat)

        if sync.successful():
            return self._cleanup()

        # We just want the name of the exception so don't bother with
        # sys.exc_info()
        self.log.error('mail sync should run forever',
                       provider=self.provider_name,
                       account_id=self.account_id,
                       exception=type(sync.exception).__name__)
        raise sync.exception

    def process_command(self, cmd):
        """ Returns True if successful, or False if process should abort. """
        self.log.info('processing command', cmd=cmd)
        return cmd != 'shutdown'

    def sync(self):
        raise NotImplementedError

    def _cleanup(self):
        with session_scope(self.namespace_id) as mailsync_db_session:
            map(lambda x: x.set_stopped(mailsync_db_session),
                self.folder_monitors)
        self.folder_monitors.kill()
        clear_heartbeat_status(self.account_id)


def thread_polling(thread):
    return getattr(thread, 'state') == 'poll'
