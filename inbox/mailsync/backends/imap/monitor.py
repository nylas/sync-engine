from gevent import sleep
from gevent.pool import Group
from gevent.coros import BoundedSemaphore
from sqlalchemy.orm.exc import NoResultFound
from inbox.basicauth import ValidationError
from nylas.logging import get_logger
from inbox.crispin import retry_crispin, connection_pool
from inbox.models import Account, Folder
from inbox.models.constants import MAX_FOLDER_NAME_LENGTH
from inbox.mailsync.backends.base import BaseMailSyncMonitor
from inbox.mailsync.backends.base import (MailsyncError,
                                          mailsync_session_scope,
                                          thread_polling, thread_finished)
from inbox.mailsync.backends.imap.generic import FolderSyncEngine
from inbox.heartbeat.status import clear_heartbeat_status
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
    def __init__(self, account,
                 heartbeat=1, refresh_frequency=30):
        self.refresh_frequency = refresh_frequency
        self.syncmanager_lock = BoundedSemaphore(1)
        self.saved_remote_folders = None
        self.sync_engine_class = FolderSyncEngine

        self.folder_monitors = Group()

        BaseMailSyncMonitor.__init__(self, account, heartbeat)

    @retry_crispin
    def prepare_sync(self):
        """
        Gets and save Folder objects for folders on the IMAP backend. Returns a
        list of tuples (folder_name, folder_id) for each folder we want to sync
        (in order).
        """
        with mailsync_session_scope() as db_session:
            with connection_pool(self.account_id).get() as crispin_client:
                # Get a fresh list of the folder names from the remote
                remote_folders = crispin_client.folders()
                if self.saved_remote_folders != remote_folders:
                    self.save_folder_names(db_session, remote_folders)
                    self.saved_remote_folders = remote_folders
                # The folders we should be syncing
                sync_folders = crispin_client.sync_folders()

            sync_folder_names_ids = []
            for folder_name in sync_folders:
                try:
                    id_, = db_session.query(Folder.id). \
                        filter(Folder.name == folder_name,
                               Folder.account_id == self.account_id).one()
                    sync_folder_names_ids.append((folder_name, id_))
                except NoResultFound:
                    log.error('Missing Folder object when starting sync',
                              folder_name=folder_name)
                    raise MailsyncError("Missing Folder '{}' on account {}"
                                        .format(folder_name, self.account_id))
            return sync_folder_names_ids

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
            db_session.delete(local_folders[name])
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

    def start_new_folder_sync_engines(self, folders=set()):
        new_folders = [f for f in self.prepare_sync() if f not in folders]
        for folder_name, folder_id in new_folders:
            log.info('Folder sync engine started',
                     account_id=self.account_id,
                     folder_id=folder_id,
                     folder_name=folder_name)
            thread = self.sync_engine_class(self.account_id,
                                            folder_name,
                                            folder_id,
                                            self.email_address,
                                            self.provider_name,
                                            self.syncmanager_lock)
            self.folder_monitors.start(thread)
            while not thread_polling(thread) and \
                    not thread_finished(thread) and \
                    not thread.ready():
                sleep(self.heartbeat)

            # allow individual folder sync monitors to shut themselves down
            # after completing the initial sync
            if thread_finished(thread) or thread.ready():
                if thread.exception:
                    # Exceptions causing the folder sync to exit should not
                    # clear the heartbeat.
                    log.info('Folder sync engine exited with error',
                             account_id=self.account_id,
                             folder_id=folder_id,
                             folder_name=folder_name,
                             error=thread.exception)
                else:
                    log.info('Folder sync engine finished',
                             account_id=self.account_id,
                             folder_id=folder_id,
                             folder_name=folder_name)
                    # clear the heartbeat for this folder-thread since it
                    # exited cleanly.
                    clear_heartbeat_status(self.account_id, folder_id)

                # note: thread is automatically removed from
                # self.folder_monitors
            else:
                folders.add((folder_name, folder_id))

    def start_delete_handler(self):
        self.delete_handler = DeleteHandler(account_id=self.account_id,
                                            namespace_id=self.namespace_id,
                                            uid_accessor=lambda m: m.imapuids)
        self.delete_handler.start()

    def sync(self):
        try:
            self.start_delete_handler()
            folders = set()
            self.start_new_folder_sync_engines(folders)
            while True:
                sleep(self.refresh_frequency)
                self.start_new_folder_sync_engines(folders)
        except ValidationError as exc:
            log.error(
                'Error authenticating; stopping sync', exc_info=True,
                account_id=self.account_id, logstash_tag='mark_invalid')
            with mailsync_session_scope() as db_session:
                account = db_session.query(Account).get(self.account_id)
                account.mark_invalid()
                account.update_sync_error(str(exc))
