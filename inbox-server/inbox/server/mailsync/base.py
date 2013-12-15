import zerorpc

from gevent import Greenlet, joinall, sleep
from gevent.queue import Queue, Empty

from ..config import config
from ..log import configure_sync_logging

from .exc import SyncException

def verify_db(crispin_client, db_session):
    pass

def trigger_index_update(namespace_id):
    c = zerorpc.Client()
    c.connect(config.get('SEARCH_SERVER_LOC', None))
    c.index(namespace_id)

def gevent_check_join(log, threads, errmsg):
    """ Block until all threads have completed and throw an error if threads
        are not successful.
    """
    joinall(threads)
    errors = [thread.exception for thread in threads if not thread.successful()]
    if errors:
        log.error(errmsg)
        for error in errors:
            log.error(error)
        raise SyncException("Fatal error encountered")

class BaseMailSyncMonitor(Greenlet):
    def __init__(self, account_id, email_address, provider, status_cb,
            heartbeat=1):
        self.inbox = Queue()
        # how often to check inbox, in seconds
        self.heartbeat = heartbeat
        self.log = configure_sync_logging(account_id)
        self.account_id = account_id
        self.email_address = email_address
        self.provider = provider

        # Stuff that might be updated later and we want to keep a shared
        # reference on child greenlets.
        if hasattr(self, 'shared_state'):
            self.shared_state['status_cb'] = status_cb
        else:
            self.shared_state = dict(status_cb=status_cb)

        Greenlet.__init__(self)

    def _run(self):
        sync = Greenlet.spawn(self.sync)
        while not sync.ready():
            try:
                cmd = self.inbox.get_nowait()
                if not self.process_command(cmd):
                    self.log.info("Stopping sync for {0}".format(
                        self.email_address))
                    # ctrl-c, basically!
                    for monitor in self.folder_monitors:
                        monitor.kill(block=True)
                    sync.kill(block=True)
                    return
            except Empty:
                sleep(self.heartbeat)
        assert not sync.successful(), "mail sync should run forever!"
        raise sync.exception

    def process_command(self, cmd):
        """ Returns True if successful, or False if process should abort. """
        self.log.info("processing command {0}".format(cmd))
        return cmd != 'shutdown'

    def _thread_finished(self, thread):
        state = getattr(thread, 'state')
        return state == 'finish'

    def _thread_polling(self, thread):
        state = getattr(thread, 'state')
        return state is not None and state.startswith('poll')

    def sync(self):
        raise NotImplementedError
