import zerorpc

from gevent import Greenlet, joinall, sleep
from gevent.queue import Queue, Empty

from ..config import config
from ..log import configure_sync_logging

from .exc import SyncException

def verify_db(crispin_client, db_session):
    pass

def check_folder_name(log, inbox_folder, old_folder_name, new_folder_name):
    if old_folder_name is not None and \
            new_folder_name != old_folder_name:
        msg = "{0} folder name changed from '{1}' to '{2}'".format(
                inbox_folder, old_folder_name, new_folder_name)
        raise SyncException(msg)

def save_folder_names(log, account, folder_names, db_session):
    # NOTE: We don't do anything like canonicalizing to lowercase because
    # different backends may be case-sensitive or not. Code that references
    # saved folder names should canonicalize if needed when doing comparisons.
    assert 'inbox' in folder_names, "account {0} has no detected Inbox".format(
            account.email_address)
    check_folder_name(log, 'inbox', account.inbox_folder_name,
            folder_names['inbox'])
    account.inbox_folder_name = folder_names['inbox']
    # We allow accounts not to have archive / sent folders; it's up to the mail
    # sync code for the account type to figure out what to do in this
    # situation.
    if 'archive' in folder_names:
        check_folder_name(log, 'archive', account.archive_folder_name,
                folder_names['archive'])
        account.archive_folder_name = folder_names['archive']
    if 'sent' in folder_names:
        check_folder_name(log, 'sent', account.sent_folder_name,
                folder_names['sent'])
        account.sent_folder_name = folder_names['sent']
    db_session.commit()

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
