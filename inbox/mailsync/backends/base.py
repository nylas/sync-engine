from gc import collect as garbage_collect

import zerorpc
from gevent import Greenlet, joinall, sleep
from gevent.queue import Queue, Empty
from sqlalchemy.exc import DataError

from inbox.util.concurrency import retry_wrapper
from inbox.util.itert import partition
from inbox.util.misc import load_modules
from inbox.config import config
from inbox.log import configure_mailsync_logging
from inbox.models import (Account, Folder, MAX_FOLDER_NAME_LENGTH)
from inbox.mailsync.exc import SyncException
import inbox.mailsync.backends


class MailsyncError(Exception):
    pass


def register_backends():
    """
    Finds the monitor modules for the different providers
    (in the backends directory) and imports them.

    Creates a mapping of provider:monitor for each backend found.
    """
    monitor_cls_for = {}

    # Find and import
    modules = load_modules(inbox.mailsync.backends)

    # Create mapping
    for module in modules:
        if hasattr(module, 'PROVIDER'):
            provider = module.PROVIDER

            assert hasattr(module, 'SYNC_MONITOR_CLS')
            monitor_cls = getattr(module, module.SYNC_MONITOR_CLS, None)

            assert monitor_cls is not None

            monitor_cls_for[provider] = (monitor_cls, module)

    return monitor_cls_for


def verify_folder_name(account_id, old, new):
    if old is not None and old.name != new.name:
        raise SyncException(
            "Core folder on account {} changed name from '{}' to '{}'".format(
                account_id, old.name, new.name))
    return new


def save_folder_names(log, account, folder_names, db_session):
    """
    Create Folder objects & map special folder names on Account objects.

    Folders that belong to an account and no longer exist in `folder_names`
    ARE DELETED.
    """
    # NOTE: We don't do anything like canonicalizing to lowercase because
    # different backends may be case-sensitive or not. Code that references
    # saved folder names should canonicalize if needed when doing comparisons.

    assert 'inbox' in folder_names, 'Account {} has no detected inbox folder'\
        .format(account.email_address)

    folders = {f.name.lower(): f for f in
               db_session.query(Folder).filter_by(account=account)}

    for canonical_name in ['inbox', 'drafts', 'sent', 'spam', 'trash',
                           'starred', 'important', 'archive', 'all']:
        if canonical_name in folder_names:
            backend_folder_name = folder_names[canonical_name].lower()
            if backend_folder_name not in folders:
                folder = Folder.create(account, folder_names[canonical_name],
                                       db_session,
                                       canonical_name)
                attr_name = '{}_folder'.format(canonical_name)
                setattr(account, attr_name, verify_folder_name(
                    account.id, getattr(account, attr_name), folder))
            else:
                del folders[backend_folder_name]

    # Gmail labels, user-created IMAP/EAS folders, etc.
    if 'extra' in folder_names:
        for name in folder_names['extra']:
            name = name[:MAX_FOLDER_NAME_LENGTH]
            if name.lower() not in folders:
                folder = Folder.create(account, name, db_session)
                db_session.add(folder)
            if name.lower() in folders:
                del folders[name.lower()]

    # This may cascade to FolderItems and ImapUid (ONLY), which is what we
    # want--doing the update here short-circuits us syncing that change later.
    log.info("Folders were deleted from the remote: {}".format(folders.keys()))
    for folder in folders.values():
        db_session.delete(folder)
        # TODO(emfree) delete associated tag

    # Create associated tags for any new folders.
    for folder in account.folders:
        folder.get_associated_tag(db_session)

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
    errors = [thread.exception for thread in threads
              if not thread.successful()]
    if errors:
        log.error(errmsg)
        for error in errors:
            log.error(error)
        raise SyncException("Fatal error encountered")


def create_db_objects(account_id, db_session, log, folder_name, raw_messages,
                      msg_create_fn):
    new_uids = []
    # TODO: Detect which namespace to add message to. (shared folders)
    # Look up message thread,
    acc = db_session.query(Account).get(account_id)
    folder = Folder.find_or_create(db_session, acc, folder_name)
    for msg in raw_messages:
        uid = msg_create_fn(db_session, log, acc, folder, msg)
        if uid is not None:
            new_uids.append(uid)

    # imapuid, message, thread, labels
    return new_uids


def commit_uids(db_session, log, new_uids):
    new_messages = [item.message for item in new_uids]

    # Save message part blobs before committing changes to db.
    for msg in new_messages:
        threads = [Greenlet.spawn(retry_wrapper, lambda: part.save(part._data),
                                  log)
                   for part in msg.parts if hasattr(part, '_data')]
        # Fatally abort if part saves error out. Messages in this
        # chunk will be retried when the sync is restarted.
        gevent_check_join(log, threads,
                          "Could not save message parts to blob store!")
        # clear data to save memory
        for part in msg.parts:
            part._data = None

    garbage_collect()

    try:
        log.info("Committing {0} UIDs".format(len(new_uids)))
        db_session.add_all(new_uids)
        db_session.commit()
    except DataError as e:
        db_session.rollback()
        log.error("Issue inserting new UIDs into database. "
                  "This probably means that an object's property is "
                  "malformed or way too long, etc.")

        for uid in new_uids:
            log.error(uid)
            import inspect
            from pprint import pformat
            log.error(inspect.getmembers(uid))
            try:
                log.error(pformat(uid.__dict__, indent=2))
            except AttributeError:
                pass

            for part in uid.message.parts:
                log.error(inspect.getmembers(part))
                try:
                    log.error(pformat(part.__dict__, indent=2))
                except AttributeError:
                    pass

        raise e

    # NOTE: indexing temporarily disabled because xapian is leaking fds :/
    # trigger_index_update(self.account.namespace.id)


def new_or_updated(uids, local_uids):
    """ HIGHESTMODSEQ queries return a list of messages that are *either*
        new *or* updated. We do different things with each, so we need to
        sort out which is which.
    """
    return partition(lambda x: x in local_uids, uids)


class BaseMailSyncMonitor(Greenlet):
    def __init__(self, account_id, email_address, provider, status_cb,
                 heartbeat=1):
        self.inbox = Queue()
        # how often to check inbox, in seconds
        self.heartbeat = heartbeat
        self.log = configure_mailsync_logging(account_id)
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
        return retry_wrapper(self._run_impl, self.log,
                             account_id=self.account_id)

    def _run_impl(self):
        sync = Greenlet.spawn(retry_wrapper, self.sync, self.log,
                              account_id=self.account_id)
        while not sync.ready():
            try:
                cmd = self.inbox.get_nowait()
                if not self.process_command(cmd):
                    # ctrl-c, basically!
                    self.log.info("Stopping sync for {0}".format(
                        self.email_address))
                    # make sure the parent can't start/stop any folder monitors
                    # first
                    sync.kill(block=True)
                    self.folder_monitors.kill()
                    return
            except Empty:
                sleep(self.heartbeat)
        assert not sync.successful(), \
            "mail sync for {} account {} should run forever!"\
            .format(self.provider, self.account_id)
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
