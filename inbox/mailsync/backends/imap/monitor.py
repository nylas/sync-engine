from gevent import sleep
from gevent.pool import Group
from gevent.coros import BoundedSemaphore
from inbox.basicauth import ValidationError
from nylas.logging import get_logger
from inbox.crispin import retry_crispin, connection_pool
from inbox.models import Account, Folder, Category
from inbox.models.constants import MAX_FOLDER_NAME_LENGTH
from inbox.models.session import session_scope
from inbox.mailsync.backends.base import BaseMailSyncMonitor
from inbox.mailsync.backends.imap.generic import FolderSyncEngine
from inbox.mailsync.gc import DeleteHandler
log = get_logger()


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
        self.exiting = False

        BaseMailSyncMonitor.__init__(self, account, heartbeat)

    @retry_crispin
    def ensure_folders_synced(self, remote_folders):
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
        assert 'inbox' in {f.role for f in remote_folders},\
            'Account {} has no detected inbox folder'.\
            format(self.email_address)

        if self.saved_remote_folders != remote_folders:
            with session_scope(self.namespace_id) as db_session:
                self.perform_folder_sync(db_session, remote_folders)
                self.saved_remote_folders = remote_folders

    def perform_folder_sync(self, db_session, remote_folders):
        local_folders = db_session.query(Folder).filter(Folder.account_id == self.account_id)
        local_byname = {f.name: f for f in local_folders}

        remote_byname = {f.display_name.rstrip()[:MAX_FOLDER_NAME_LENGTH]: f for f in remote_folders}
        deleted_names = set(local_byname) - set(remote_byname)

        # Delete folders no longer present on the remote.
        # Note that the folder with canonical_name='inbox' cannot be deleted;
        # remote_folder_names will always contain an entry corresponding to it.
        for name in deleted_names:
            if local_folders[name].category_id is not None:
                cat = db_session.query(Category).get(
                    local_folders[name].category_id)
                if cat is not None:
                    db_session.delete(cat)
            del local_folders[name]

        # Create new folders
        account = None
        for name, folder in remote_byname.iteritems():
            if name in local_byname:
                continue
            if not account:
                account = db_session.query(Account).get(self.account_id)
            Folder.find_or_create(db_session, account, folder.display_name, folder.role)

        # Set the should_run bit for existing folders to True (it's True by
        # default for new ones.)
        for f in local_folders.values():
            if f.imapsyncstatus:
                f.imapsyncstatus.sync_should_run = True

        db_session.commit()

    def sync_folders_and_ensure_monitors(self):
        # Grab info from the db and the IMAP server, ensure that folders are
        # all up-to-date.
        with connection_pool(self.account_id).get() as crispin_client:
            remote_folders = crispin_client.folders()
            folder_names_to_sync = crispin_client.sync_folders()

        self.ensure_folders_synced(remote_folders)

        monitors_byname = {m.folder_name: m for m in self.folder_monitors}

        for folder_name in folder_names_to_sync:
            if folder_name not in monitors_byname:
                thread = self.sync_engine_class(self.account_id,
                                                self.namespace_id,
                                                folder_name,
                                                self.email_address,
                                                self.provider_name,
                                                self.syncmanager_lock)
                thread.link_exception(self.folder_monitor_raised_cb)
                thread.link_value(self.folder_monitor_finished_cb)
                self.folder_monitors.start(thread)

    def folder_monitor_raised_cb(self, thread):
        self.stop_sync_with_error(thread.exception, thread.folder_name)

    def folder_monitor_finished_cb(self, thread):
        log.info('Greenlet exited gracefully', message=thread.value.message,
                 account_id=self.account_id)

    def start_delete_handler(self):
        if self.delete_handler is None:
            self.delete_handler = DeleteHandler(
                account_id=self.account_id,
                namespace_id=self.namespace_id,
                provider_name=self.provider_name,
                uid_accessor=lambda m: m.imapuids)
            self.delete_handler.start()

    def stop_sync_with_error(self, exc, folder_name=None):
        log.error('Sync halting with exception', folder_name=folder_name,
                  exc_info=True, exc=exc, account_id=self.account_id)

        with session_scope(self.namespace_id) as db_session:
            account = db_session.query(Account).get(self.account_id)
            account.disable_sync(reason='Sync Error ({})'.format(folder_name), exception=exc)

            if isinstance(exc, ValidationError):
                account.mark_invalid(exc.message)
            else:
                account.mark_stopped()

        self.folder_monitors.kill(block=False)
        self.delete_handler.kill(block=False)
        self.exiting = True

    def sync(self):
        try:
            self.start_delete_handler()
            while not self.exiting:
                self.sync_folders_and_ensure_monitors()
                sleep(self.refresh_frequency)
        except ValidationError as exc:
            self.stop_sync_with_error(exc)
