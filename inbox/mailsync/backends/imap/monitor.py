from datetime import datetime

from gevent import sleep
from gevent.pool import Group
from gevent.coros import BoundedSemaphore
from gevent.event import Event
from sqlalchemy.orm import load_only

from nylas.logging import get_logger
log = get_logger()
from inbox.basicauth import ValidationError
from inbox.crispin import retry_crispin, connection_pool
from inbox.models import Account, Folder, Category
from inbox.models.constants import MAX_FOLDER_NAME_LENGTH
from inbox.models.session import session_scope
from inbox.mailsync.backends.base import BaseMailSyncMonitor
from inbox.mailsync.backends.imap.generic import FolderSyncEngine
from inbox.mailsync.backends.imap.s3 import S3FolderSyncEngine
from inbox.mailsync.gc import DeleteHandler


class ImapSyncMonitor(BaseMailSyncMonitor):
    """
    Top-level controller for an account's mail sync. Spawns individual
    FolderSync greenlets for each folder.

    Parameters
    ----------
    heartbeat: Integer
        Seconds to wait between checking on folder sync threads.
    (DEPRECATED) refresh_frequency: Integer
        Seconds to wait between checking for new folders to sync.
    syncback_frequency: Integer
        Seconds to wait between performing consecutive syncback iterations and
        checking for new folders to sync.

    """
    def __init__(self, account, heartbeat=1, refresh_frequency=30,
                 syncback_frequency=5):
        # DEPRECATED.
        # TODO[k]: Remove after sync-syncback integration deploy is complete.
        self.refresh_frequency = refresh_frequency
        self.syncmanager_lock = BoundedSemaphore(1)
        self.saved_remote_folders = None
        self.sync_engine_class = FolderSyncEngine
        self.folder_monitors = Group()

        self.delete_handler = None

        self.syncback_handler = None
        self.folder_sync_signals = {}
        self.syncback_timestamp = None
        self.syncback_frequency = syncback_frequency

        BaseMailSyncMonitor.__init__(self, account, heartbeat)

    @retry_crispin
    def prepare_sync(self):
        """
        Gets and save Folder objects for folders on the IMAP backend. Returns a
        list of folder names for the folders we want to sync (in order).

        """
        with connection_pool(self.account_id).get() as crispin_client:
            # Get a fresh list of the folder names from the remote
            remote_folders = crispin_client.folders()
            # The folders we should be syncing
            sync_folders = crispin_client.sync_folders()

        if self.saved_remote_folders != remote_folders:
            with session_scope(self.namespace_id) as db_session:
                self.save_folder_names(db_session, remote_folders)
                self.saved_remote_folders = remote_folders
        return sync_folders

    def save_folder_names(self, db_session, raw_folders):
        """
        Save the folders present on the remote backend for an account.

        * Create Folder objects.
        * Delete Folders that no longer exist on the remote.

        Notes
        -----
        Generic IMAP uses folders (not labels).
        Canonical folders ('inbox') and other folders are created as Folder
        objects only accordingly.

        We don't canonicalize folder names to lowercase when saving because
        different backends may be case-sensitive or otherwise - code that
        references saved folder names should canonicalize if needed when doing
        comparisons.

        """
        account = db_session.query(Account).get(self.account_id)
        remote_folder_names = {f.display_name.rstrip()[:MAX_FOLDER_NAME_LENGTH]
                               for f in raw_folders}

        assert 'inbox' in {f.role for f in raw_folders},\
            'Account {} has no detected inbox folder'.\
            format(account.email_address)

        local_folders = {f.name: f for f in db_session.query(Folder).filter(
                         Folder.account_id == self.account_id)}

        # Delete folders no longer present on the remote.
        # Note that the folder with canonical_name='inbox' cannot be deleted;
        # remote_folder_names will always contain an entry corresponding to it.
        discard = set(local_folders) - remote_folder_names
        for name in discard:
            log.info('Folder deleted from remote', account_id=self.account_id,
                     name=name)
            if local_folders[name].category_id is not None:
                cat = db_session.query(Category).get(
                    local_folders[name].category_id)
                if cat is not None:
                    db_session.delete(cat)
            del local_folders[name]

        # Create new folders
        for raw_folder in raw_folders:
            Folder.find_or_create(db_session, account, raw_folder.display_name,
                                  raw_folder.role)
        # Set the should_run bit for existing folders to True (it's True by
        # default for new ones.)
        for f in local_folders.values():
            if f.imapsyncstatus:
                f.imapsyncstatus.sync_should_run = True

        db_session.commit()

    def start_new_folder_sync_engines(self):
        running_monitors = {monitor.folder_name: monitor for monitor in
                            self.folder_monitors}
        with session_scope(self.namespace_id) as db_session:
            account = db_session.query(Account).options(
                load_only('_sync_status')).get(self.account_id)
            s3_resync = account._sync_status.get('s3_resync', False)

        for folder_name in self.prepare_sync():
            if folder_name in running_monitors:
                thread = running_monitors[folder_name]
            else:
                log.info('Folder sync engine started',
                         account_id=self.account_id, folder_name=folder_name)
                self._add_sync_signal(folder_name)
                thread = self.sync_engine_class(self.account_id,
                                                self.namespace_id,
                                                folder_name,
                                                self.email_address,
                                                self.provider_name,
                                                self.syncmanager_lock,
                                                self.folder_sync_signals[folder_name])
                self.folder_monitors.start(thread)

                if s3_resync:
                    log.info('Starting an S3 monitor',
                             account_id=self.account_id)
                    s3_thread = S3FolderSyncEngine(self.account_id,
                                                   self.namespace_id,
                                                   folder_name,
                                                   self.email_address,
                                                   self.provider_name,
                                                   self.syncmanager_lock)

                    self.folder_monitors.start(s3_thread)

            while not thread.state == 'poll' and not thread.ready():
                sleep(self.heartbeat)
                self.perform_syncback()

            if thread.ready():
                self._remove_sync_signal[folder_name]
                log.info('Folder sync engine exited',
                         account_id=self.account_id,
                         folder_name=folder_name,
                         error=thread.exception)

    def start_delete_handler(self):
        if self.delete_handler is None:
            self.delete_handler = DeleteHandler(
                account_id=self.account_id,
                namespace_id=self.namespace_id,
                provider_name=self.provider_name,
                uid_accessor=lambda m: m.imapuids)
            self.delete_handler.start()

    def perform_syncback(self):
        """
        Perform syncback for the account.

        Syncback is performed iff all folder syncs are paused, and the previous
        syncback occurred more than syncback_frequency seconds ago.

        The first condition is checked by the call to _can_syncback().
        The second condition is needed because if there are a large number of
        pending actions during initial sync, it could repeatedly get interrupted
        and put on hold for seconds at a time.

        """
        from inbox.syncback.base import SyncbackHandler

        if not self._can_syncback():
            log.info('Skipping syncback', reason='folder syncs running')
            return

        syncback_interval = ((datetime.utcnow() - self.syncback_timestamp).seconds if # noqa
            self.syncback_timestamp else None)

        if syncback_interval < self.syncback_frequency:
            log.info('Skipping syncback',
                     reason='last syncback < syncback_frequency seconds ago',
                     syncback_frequency=self.syncback_frequency)
            # Reset here so syncs can proceed
            self._signal_syncs()
            return

        if self.syncback_handler is None:
            self.syncback_handler = SyncbackHandler(self.account_id,
                                                    self.namespace_id,
                                                    self.provider_name)
        try:
            log.info('Performing syncback',
                     syncback_interval_in_seconds=syncback_interval)
            self.syncback_handler.send_client_changes()
            self.syncback_timestamp = datetime.utcnow()
        except Exception:
            # Log, set self.folder_sync_signals and then re-raise (so the
            # greenlet can be restarted etc.)
            log.error('Critical syncback error', exc_info=True)
            raise
        finally:
            # Reset here so syncs can proceed
            self._signal_syncs()

    def sync(self):
        try:
            self.start_delete_handler()
            self.start_new_folder_sync_engines()
            while True:
                sleep(self.syncback_frequency)
                self.perform_syncback()
                self.start_new_folder_sync_engines()
        except ValidationError as exc:
            log.error(
                'Error authenticating; stopping sync', exc_info=True,
                account_id=self.account_id, logstash_tag='mark_invalid')
            with session_scope(self.namespace_id) as db_session:
                account = db_session.query(Account).get(self.account_id)
                account.mark_invalid()
                account.update_sync_error(str(exc))

    def _add_sync_signal(self, folder_name):
        self.folder_sync_signals[folder_name] = Event()
        self.folder_sync_signals[folder_name].set()

    def _remove_sync_signal(self, folder_name):
        del self.folder_sync_signals[folder_name]

    def _can_syncback(self):
        """
        Determine if syncback can occur.

        If all folder syncs are paused as indicated by the folder_sync_signals,
        returns True. Else, returns False.

        """
        return (not self.folder_sync_signals or
                all(not signal.is_set() for signal in
                    self.folder_sync_signals.values()))

    def _signal_syncs(self):
        """ Indicate that folder syncs can resume. """
        for signal in self.folder_sync_signals.values():
            signal.set()
