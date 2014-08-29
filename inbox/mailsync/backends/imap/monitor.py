from gevent import sleep
from gevent.pool import Group
from inbox.log import get_logger
from inbox.models import Tag, Folder
from inbox.models.backends.imap import ImapAccount, ImapFolderSyncStatus
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
    def __init__(self, account, heartbeat=1, poll_frequency=300,
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

    def sync(self):
        """ Start per-folder syncs. Only have one per-folder sync in the
            'initial' state at a time.
        """
        with mailsync_session_scope() as db_session:
            with _pool(self.account_id).get() as crispin_client:
                sync_folders = crispin_client.sync_folders()
                account = db_session.query(ImapAccount)\
                    .get(self.account_id)
                save_folder_names(log, account,
                                  crispin_client.folder_names(), db_session)
            Tag.create_canonical_tags(account.namespace, db_session)

            folder_id_for = {name: id_ for id_, name in db_session.query(
                Folder.id, Folder.name).filter_by(account_id=self.account_id)}

            saved_states = {name: state for name, state in
                            db_session.query(Folder.name,
                                             ImapFolderSyncStatus.state)
                            .join(ImapFolderSyncStatus.folder)
                            .filter(ImapFolderSyncStatus.account_id ==
                                    self.account_id)}

        for folder_name in sync_folders:
            if folder_name not in folder_id_for:
                log.error("Missing Folder object when starting sync",
                          folder_name=folder_name, folder_id_for=folder_id_for)
                raise MailsyncError("Missing Folder '{}' on account {}"
                                    .format(folder_name, self.account_id))

            if saved_states.get(folder_name) != 'finish':
                log.info('initializing folder sync')
                # STOPSHIP(emfree): replace by appropriate base class.
                thread = self.sync_engine_class(self.account_id, folder_name,
                                                folder_id_for[folder_name],
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
