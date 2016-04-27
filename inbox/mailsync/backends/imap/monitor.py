import gevent
from gevent import sleep
from gevent.pool import Group
from gevent.coros import BoundedSemaphore
from sqlalchemy.orm import load_only
from inbox.basicauth import ValidationError

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
from inbox.syncback.base import SyncbackHandler


class ImapSyncMonitor(BaseMailSyncMonitor):
    """
    Top-level controller for an account's mail sync. Spawns individual
    FolderSync greenlets for each folder.

    Parameters
    ----------
    heartbeat: Integer
        Seconds to wait between checking on folder sync threads.
    refresh_frequency: Integer
        Seconds to wait between checking for new folders to sync.

    """
    def __init__(self, account, heartbeat=1, refresh_frequency=30):
        self.refresh_frequency = refresh_frequency
        self.syncmanager_lock = BoundedSemaphore(1)
        self.saved_remote_folders = None
        self.sync_engine_class = FolderSyncEngine

        self.folder_monitors = Group()
        self.delete_handler = None
        self.syncback_handler = None

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
                         account_id=self.account_id,
                         folder_name=folder_name)
                thread = self.sync_engine_class(self.account_id,
                                                self.namespace_id,
                                                folder_name,
                                                self.email_address,
                                                self.provider_name,
                                                self.syncmanager_lock)
                self.folder_monitors.start(thread)

<<<<<<< HEAD
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
=======
>>>>>>> v0.fvckno
            while not thread.state == 'poll' and not thread.ready():
                sleep(self.heartbeat)

            if thread.ready():
                log.info('Folder sync engine exited',
                         account_id=self.account_id,
                         folder_name=folder_name,
                         error=thread.exception)

    def stop_folder_sync_engines(self):
        if self.folder_monitors:
            gevent.killall(self.folder_monitors)

    def start_delete_handler(self):
        if self.delete_handler is None:
            self.delete_handler = DeleteHandler(
                account_id=self.account_id,
                namespace_id=self.namespace_id,
                provider_name=self.provider_name,
                uid_accessor=lambda m: m.imapuids)
            self.delete_handler.start()

    def perform_syncback(self):
        if self.syncback_handler == None:
            self.syncback_handler = SyncbackHandler(self.account_id,
                                                    self.namespace_id,
                                                    self.provider_name)
        self.syncback_handler.send_client_changes()

    def sync(self):
        try:
            self.start_delete_handler()
            self.perform_syncback()
            self.start_new_folder_sync_engines()
            while True:
                sleep(self.refresh_frequency)
                # Pause sync to perform syncback --
                # this stops running foldersyncs, performs syncback and
                # resumes them.
                self.stop_folder_sync_engines()
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
