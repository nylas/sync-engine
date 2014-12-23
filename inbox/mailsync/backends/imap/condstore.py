"""
-----------------
GENERIC IMAP SYNC ENGINE (~WITH~ COND STORE)
-----------------

Generic IMAP backend with CONDSTORE support.

No support for server-side threading, so we have to thread messages ourselves.

"""
from gevent import sleep
from inbox.crispin import retry_crispin
from inbox.mailsync.backends.base import (save_folder_names, new_or_updated,
                                          mailsync_session_scope)
from inbox.mailsync.backends.imap import common
from inbox.mailsync.backends.imap.generic import (FolderSyncEngine,
                                                  uidvalidity_cb, UIDStack)
from inbox.log import get_logger
log = get_logger()


class CondstoreFolderSyncEngine(FolderSyncEngine):
    def should_idle(self, crispin_client):
        return self.folder_name == crispin_client.folder_names()['inbox']

    def poll_impl(self):
        with self.conn_pool.get() as crispin_client:
            download_stack = UIDStack()
            self.check_uid_changes(crispin_client, download_stack,
                                   async_download=False)
            if self.should_idle(crispin_client):
                idling = True
                self.idle_wait(crispin_client)
            else:
                idling = False
        # Close IMAP connection before sleeping
        if not idling:
            sleep(self.poll_frequency)

    @retry_crispin
    def poll_for_changes(self, download_stack):
        log.new(account_id=self.account_id, folder=self.folder_name)
        while True:
            log.debug('polling for changes')
            with self.conn_pool.get() as crispin_client:
                self.check_uid_changes(crispin_client, download_stack,
                                       async_download=True)
                if self.should_idle(crispin_client):
                    idling = True
                    self.idle_wait(crispin_client)
                else:
                    idling = False
            # Close IMAP connection before sleeping
            if not idling:
                sleep(self.poll_frequency)

    def check_uid_changes(self, crispin_client, download_stack,
                          async_download):
        crispin_client.select_folder(self.folder_name, uidvalidity_cb)
        new_highestmodseq = crispin_client.selected_highestmodseq
        with mailsync_session_scope() as db_session:
            saved_folder_info = common.get_folder_info(
                self.account_id, db_session, self.folder_name)
            # Ensure that we have an initial highestmodseq value stored before
            # we begin polling for changes.
            if saved_folder_info is None or \
                    saved_folder_info.highestmodseq is None:
                assert (crispin_client.selected_uidvalidity is not None
                        and crispin_client.selected_highestmodseq is
                        not None)
                saved_folder_info = common.update_folder_info(
                    crispin_client.account_id, db_session,
                    self.folder_name,
                    crispin_client.selected_uidvalidity,
                    crispin_client.selected_highestmodseq)
            saved_highestmodseq = saved_folder_info.highestmodseq
            if new_highestmodseq == saved_highestmodseq:
                # Don't need to do anything if the highestmodseq hasn't
                # changed.
                return
            elif new_highestmodseq < saved_highestmodseq:
                # This should really never happen, but if it does, handle it.
                log.warning('got server highestmodseq less than saved '
                            'highestmodseq',
                            new_highestmodseq=new_highestmodseq,
                            saved_highestmodseq=saved_highestmodseq)
                return
            save_folder_names(log, self.account_id,
                              crispin_client.folder_names(), db_session)
        # Highestmodseq has changed, update accordingly.
        new_uidvalidity = crispin_client.selected_uidvalidity
        changed_uids = crispin_client.new_and_updated_uids(saved_highestmodseq)
        remote_uids = crispin_client.all_uids()
        with mailsync_session_scope() as db_session:
            local_uids = common.all_uids(self.account_id, db_session,
                                         self.folder_name)
        stack_uids = {uid for uid, _ in download_stack}
        local_with_pending_uids = local_uids | stack_uids
        new, updated = new_or_updated(changed_uids, local_with_pending_uids)
        if changed_uids:
            log.info("Changed UIDs", message="new: {} updated: {}"
                                             .format(len(new), len(updated)),
                     new_uid_count=len(new), updated_uid_count=len(updated))
            self.update_metadata(crispin_client, updated)
            self.highestmodseq_callback(crispin_client, new, updated,
                                        download_stack, async_download)

        with mailsync_session_scope() as db_session:
            with self.syncmanager_lock:
                self.remove_deleted_uids(db_session, local_uids, remote_uids)
            self.update_uid_counts(db_session,
                                   remote_uid_count=len(remote_uids))
            common.update_folder_info(self.account_id, db_session,
                                      self.folder_name, new_uidvalidity,
                                      new_highestmodseq)
            db_session.commit()

    def highestmodseq_callback(self, crispin_client, new_uids, updated_uids,
                               download_stack, async_download):
        for uid in sorted(new_uids):
            download_stack.put(uid, None)
        if not async_download:
            self.download_uids(crispin_client, download_stack)

    def idle_wait(self, crispin_client):
        # Idle doesn't pick up flag changes, so we don't want to
        # idle for very long, or we won't detect things like
        # messages being marked as read.
        idle_frequency = 30
        log.info('idling', timeout=idle_frequency)
        crispin_client.idle(idle_frequency)
