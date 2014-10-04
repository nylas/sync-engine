from gevent import sleep
from gevent.pool import Group
from sqlalchemy.orm.exc import NoResultFound
from inbox.log import get_logger
from inbox.models import Tag, Folder
from inbox.models.backends.imap import ImapAccount
from inbox.models.util import db_write_lock
from inbox.mailsync.backends.base import BaseMailSyncMonitor
from inbox.mailsync.backends.base import (save_folder_names,
                                          MailsyncError,
                                          mailsync_session_scope)
from inbox.mailsync.backends.imap.generic import _pool, FolderSyncEngine
from inbox.mailsync.backends.imap.condstore import CondstoreFolderSyncEngine
from inbox.providers import provider_info
log = get_logger()


class ImapSyncMonitor(BaseMailSyncMonitor):
    """ Top-level controller for an account's mail sync. Spawns individual
        FolderSync greenlets for each folder.

        Parameters
        ----------
        poll_frequency: Integer
            Seconds to wait between polling for the greenlets spawned
        heartbeat: Integer
            Seconds to wait between checking on folder sync threads.
        refresh_flags_max: Integer
            the maximum number of UIDs for which we'll check flags
            periodically.

    """
    def __init__(self, account, heartbeat=1, poll_frequency=30,
                 retry_fail_classes=[], refresh_flags_max=2000):

        self.poll_frequency = poll_frequency
        self.syncmanager_lock = db_write_lock(account.namespace.id)
        self.refresh_flags_max = refresh_flags_max

        provider_supports_condstore = provider_info(account.provider).get(
            'condstore', False)
        account_supports_condstore = getattr(account, 'supports_condstore',
                                             False)
        if provider_supports_condstore or account_supports_condstore:
            self.sync_engine_class = CondstoreFolderSyncEngine
        else:
            self.sync_engine_class = FolderSyncEngine

        self.folder_monitors = Group()

        BaseMailSyncMonitor.__init__(self, account, heartbeat,
                                     retry_fail_classes)

    def prepare_sync(self):
        """Ensures that canonical tags are created for the account, and gets
        and save Folder objects for folders on the IMAP backend. Returns a list
        of tuples (folder_name, folder_id) for each folder we want to sync (in
        order)."""
        with mailsync_session_scope() as db_session:
            account = db_session.query(ImapAccount).get(self.account_id)
            Tag.create_canonical_tags(account.namespace, db_session)
            with _pool(self.account_id).get() as crispin_client:
                sync_folders = crispin_client.sync_folders()
                save_folder_names(log, self.account_id,
                                  crispin_client.folder_names(), db_session)

            sync_folder_names_ids = []
            for folder_name in sync_folders:
                try:
                    id_, = db_session.query(Folder.id). \
                        filter(Folder.name == folder_name,
                               Folder.account_id == self.account_id).one()
                    sync_folder_names_ids.append((folder_name, id_))
                except NoResultFound:
                    log.error("Missing Folder object when starting sync",
                              folder_name=folder_name)
                    raise MailsyncError("Missing Folder '{}' on account {}"
                                        .format(folder_name, self.account_id))
            return sync_folder_names_ids

    def sync(self):
        """ Start per-folder syncs. Only have one per-folder sync in the
            'initial' state at a time.
        """
        sync_folder_names_ids = self.prepare_sync()
        for folder_name, folder_id in sync_folder_names_ids:
            log.info('initializing folder sync')
            thread = self.sync_engine_class(self.account_id,
                                            folder_name,
                                            folder_id,
                                            self.email_address,
                                            self.provider_name,
                                            self.poll_frequency,
                                            self.syncmanager_lock,
                                            self.refresh_flags_max,
                                            self.retry_fail_classes)
            thread.start()
            self.folder_monitors.add(thread)
            while not self._thread_polling(thread) and \
                    not self._thread_finished(thread) and \
                    not thread.ready():
                sleep(self.heartbeat)

            # Allow individual folder sync monitors to shut themselves down
            # after completing the initial sync.
            if self._thread_finished(thread) or thread.ready():
                log.info('folder sync finished/killed',
                         folder_name=thread.folder_name)
                # NOTE: Greenlet is automatically removed from the group.

        self.folder_monitors.join()
