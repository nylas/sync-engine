import functools

from gevent import Greenlet, joinall, sleep, GreenletExit
from gevent.queue import Queue, Empty
from sqlalchemy.exc import DataError, IntegrityError

from inbox.log import get_logger
logger = get_logger()
from inbox.util.concurrency import retry_and_report_killed
from inbox.util.itert import partition
from inbox.models import (Account, Folder, MAX_FOLDER_NAME_LENGTH)
from inbox.models.session import session_scope
from inbox.mailsync.exc import SyncException
from inbox.mailsync.reporting import report_stopped


mailsync_session_scope = functools.partial(session_scope,
                                           ignore_soft_deletes=False)


class MailsyncError(Exception):
    pass


class MailsyncDone(GreenletExit):
    pass


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
    ARE DELETED, unless they are "dangling" (do not have a 'name' set).

    We don't canonicalizing folder names to lowercase when saving
    because different backends may be case-sensitive or not. Code that
    references saved folder names should canonicalize if needed when doing
    comparisons.

    """
    assert 'inbox' in folder_names, 'Account {} has no detected inbox folder'\
        .format(account.email_address)

    all_folders = db_session.query(Folder).filter_by(
        account_id=account.id).all()
    # dangled_folders don't map to upstream account folders (may be used for
    # keeping track of e.g. special Gmail labels which are exposed as IMAP
    # flags but not folders)
    folder_for = {f.name.lower(): f for f in all_folders if f.name is not None}
    dangled_folder_for = {f.canonical_name: f for f in all_folders
                          if f.name is None}

    canonical_names = {'inbox', 'drafts', 'sent', 'spam', 'trash',
                       'starred', 'important', 'archive', 'all'}
    for canonical_name in canonical_names:
        if canonical_name in folder_names:
            backend_folder_name = folder_names[canonical_name].lower()
            if backend_folder_name not in folder_for:
                # Reconcile dangled folders which now exist on the remote
                if canonical_name in dangled_folder_for:
                    folder = dangled_folder_for[canonical_name]
                    folder.name = folder_names[canonical_name]
                    del dangled_folder_for[canonical_name]
                else:
                    folder = Folder.create(account,
                                           folder_names[canonical_name],
                                           db_session, canonical_name)
                attr_name = '{}_folder'.format(canonical_name)
                setattr(account, attr_name, verify_folder_name(
                    account.id, getattr(account, attr_name), folder))
            else:
                del folder_for[backend_folder_name]

    # Gmail labels, user-created IMAP/EAS folders, etc.
    if 'extra' in folder_names:
        for name in folder_names['extra']:
            name = name[:MAX_FOLDER_NAME_LENGTH]
            if name.lower() not in folder_for:
                # Folder.create() takes care of adding to the session
                folder = Folder.create(account, name, db_session)
            if name.lower() in folder_for:
                del folder_for[name.lower()]

    # This may cascade to FolderItems and ImapUid (ONLY), which is what we
    # want--doing the update here short-circuits us syncing that change later.
    log.info("folders deleted from remote", folders=folder_for.keys())
    for name, folder in folder_for.iteritems():
        db_session.delete(folder)
        # TODO(emfree) delete associated tag

    # Create associated tags for any new folders.
    for folder in account.folders:
        folder.get_associated_tag(db_session)

    db_session.commit()


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
                      msg_create_fn, canonical_name=None):
    new_uids = []
    # TODO: Detect which namespace to add message to. (shared folders)
    # Look up message thread,
    acc = db_session.query(Account).get(account_id)

    folder = Folder.find_or_create(db_session, acc, folder_name,
                                   canonical_name)

    for msg in raw_messages:
        uid = msg_create_fn(db_session, acc, folder, msg)
        # Must ensure message objects are flushed because they reference
        # threads, which may be new, and later messages may need to belong to
        # the same thread. If we don't flush here and disable autoflush within
        # the message creation to avoid flushing incomplete messages, we can't
        # query for the (uncommitted) new thread id.
        #
        # We should probably refactor this later to use provider-specific
        # Message constructors to avoid creating incomplete objects in the
        # first place.
        db_session.add(uid)
        db_session.flush()
        if uid is not None:
            new_uids.append(uid)

    # imapuid, message, thread, labels
    return new_uids


def commit_uids(db_session, log, new_uids):
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


def new_or_updated(uids, local_uids):
    """ HIGHESTMODSEQ queries return a list of messages that are *either*
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
    retry_fail_classes : list
        Additional exceptions to *not* retry on. (This base class sets some
        defaults.)
    """
    RETRY_FAIL_CLASSES = [MailsyncError, ValueError, AttributeError, DataError,
                          IntegrityError, TypeError]

    def __init__(self, account, heartbeat=1, retry_fail_classes=[]):
        self.inbox = Queue()
        # how often to check inbox, in seconds
        self.heartbeat = heartbeat
        self.log = logger.new(component='mail sync', account_id=account.id)
        self.account_id = account.id
        self.email_address = account.email_address
        self.provider_name = account.provider
        self.retry_fail_classes = self.RETRY_FAIL_CLASSES
        self.retry_fail_classes.extend(retry_fail_classes)

        # Stuff that might be updated later and we want to keep a shared
        # reference on child greenlets.
        if not hasattr(self, 'shared_state'):
            self.shared_state = dict()

        Greenlet.__init__(self)
        self.link_value(lambda _: report_stopped(self.account_id))

    def _run(self):
        return retry_and_report_killed(self._run_impl,
                                       account_id=self.account_id,
                                       logger=self.log,
                                       fail_classes=self.retry_fail_classes)

    def _run_impl(self):
        sync = Greenlet(retry_and_report_killed, self.sync,
                        account_id=self.account_id, logger=self.log)
        sync.link_value(lambda _: report_stopped(account_id=self.account_id))
        sync.start()
        while not sync.ready():
            try:
                cmd = self.inbox.get_nowait()
                if not self.process_command(cmd):
                    # ctrl-c, basically!
                    self.log.info("Stopping sync", email=self.email_address)
                    # make sure the parent can't start/stop any folder monitors
                    # first
                    sync.kill(block=True)
                    self.folder_monitors.kill()
                    return
            except Empty:
                sleep(self.heartbeat)

        if sync.successful():
            self.folder_monitors.kill()
            return

        self.log.error("mail sync should run forever",
                       provider=self.provider_name,
                       account_id=self.account_id)
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
