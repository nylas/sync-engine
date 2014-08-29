"""
-----------------
GENERIC IMAP SYNC ENGINE (~WITH~ COND STORE)
-----------------

Generic IMAP backend with CONDSTORE support.

No support for server-side threading, so we have to thread messages ourselves.

"""
from gevent import sleep
from inbox.mailsync.backends.base import (save_folder_names, new_or_updated,
                                          mailsync_session_scope)
from inbox.mailsync.backends.imap import common
from inbox.mailsync.backends.imap.generic import (FolderSyncEngine,
                                                  uidvalidity_cb,
                                                  uid_list_to_stack)
from inbox.models.backends.imap import ImapAccount
from inbox.log import get_logger
log = get_logger()

IDLE_FOLDERS = ['inbox', 'sent mail']


class CondstoreFolderSyncEngine(FolderSyncEngine):
    def initial_sync_impl(self, crispin_client, local_uids,
                          uid_download_stack):
        with mailsync_session_scope() as db_session:
            saved_folder_info = common.get_folder_info(self.account_id,
                                                       db_session,
                                                       self.folder_name)

            if saved_folder_info is None:
                assert (crispin_client.selected_uidvalidity is not None and
                        crispin_client.selected_highestmodseq is not None)

                common.update_folder_info(
                    crispin_client.account_id, db_session, self.folder_name,
                    crispin_client.selected_uidvalidity,
                    crispin_client.selected_highestmodseq)

            self.__check_flags(crispin_client, db_session, local_uids)
        return FolderSyncEngine.initial_sync_impl(
            self, crispin_client, local_uids, uid_download_stack,
            spawn_flags_refresh_poller=False)

    def poll_impl(self, crispin_client):
        log.bind(state='poll')

        with mailsync_session_scope() as db_session:
            saved_folder_info = common.get_folder_info(
                crispin_client.account_id, db_session, self.folder_name)

            saved_highestmodseq = saved_folder_info.highestmodseq

        # Start a session since we're going to IDLE below anyway...
        # This also resets the folder name cache, which we want in order to
        # detect folder/label additions and deletions.
        status = crispin_client.select_folder(
            self.folder_name, uidvalidity_cb(crispin_client.account_id))

        log.debug(current_modseq=status['HIGHESTMODSEQ'],
                  saved_modseq=saved_highestmodseq)

        if status['HIGHESTMODSEQ'] > saved_highestmodseq:
            with mailsync_session_scope() as db_session:
                acc = db_session.query(ImapAccount).get(self.account_id)
                save_folder_names(log, acc, crispin_client.folder_names(),
                                  db_session)
            self.highestmodseq_update(crispin_client, saved_highestmodseq)

        # We really only want to idle on a folder for new messages. Idling on
        # `All Mail` won't tell us when messages are archived from the Inbox
        if self.folder_name.lower() in IDLE_FOLDERS:
            status = crispin_client.select_folder(
                self.folder_name, uidvalidity_cb(crispin_client.account_id))
            # Idle doesn't pick up flag changes, so we don't want to idle for
            # very long, or we won't detect things like messages being marked
            # as read.
            idle_frequency = 30

            log.info('idling', timeout=idle_frequency)
            crispin_client.conn.idle()
            crispin_client.conn.idle_check(timeout=idle_frequency)

            # If we want to do something with the response, but lousy
            # because it uses sequence IDs instead of UIDs
            # resp = c.idle_check(timeout=shared_state['poll_frequency'])
            # r = dict( EXISTS=[], EXPUNGE=[])
            # for msg_uid, cmd in resp:
            #     r[cmd].append(msg_uid)
            # print r

            crispin_client.conn.idle_done()
            log.info('IDLE triggered poll')
        else:
            log.info('IDLE sleeping', seconds=self.poll_frequency)
            sleep(self.poll_frequency)

    def highestmodseq_update(self, crispin_client, last_highestmodseq):
        new_highestmodseq = crispin_client.selected_highestmodseq
        new_uidvalidity = crispin_client.selected_uidvalidity
        log.info('starting highestmodseq update',
                 current_highestmodseq=new_highestmodseq)
        changed_uids = crispin_client.new_and_updated_uids(last_highestmodseq)
        remote_uids = crispin_client.all_uids()

        local_uids = None
        if changed_uids:
            with mailsync_session_scope() as db_session:
                local_uids = common.all_uids(self.account_id, db_session,
                                             self.folder_name)

            new, updated = new_or_updated(changed_uids, local_uids)
            log.info(new_uid_count=len(new), updated_uid_count=len(updated))

            local_uids.update(new)
            with self.syncmanager_lock:
                log.debug("highestmodseq_update acquired syncmanager_lock")
                with mailsync_session_scope() as db_session:
                    deleted_uids = self.remove_deleted_uids(
                        db_session, local_uids, remote_uids)

            local_uids = local_uids - deleted_uids
            self.update_metadata(crispin_client, updated)

            with mailsync_session_scope() as db_session:
                self.update_uid_counts(
                    db_session,
                    remote_uid_count=len(remote_uids),
                    download_uid_count=len(new),
                    update_uid_count=len(updated),
                    delete_uid_count=len(deleted_uids))

            self.highestmodseq_callback(crispin_client, new, updated)
        else:
            log.info("No new or updated messages")

        with mailsync_session_scope() as db_session:
            with self.syncmanager_lock:
                log.debug("highestmodseq_update acquired syncmanager_lock")
                if local_uids is None:
                    local_uids = common.all_uids(
                        self.account_id, db_session, self.folder_name)
                deleted_uids = self.remove_deleted_uids(
                    db_session, local_uids, remote_uids)
            self.update_uid_counts(db_session,
                                   remote_uid_count=len(remote_uids),
                                   delete_uid_count=len(deleted_uids))
            common.update_folder_info(self.account_id, db_session,
                                      self.folder_name, new_uidvalidity,
                                      new_highestmodseq)
            db_session.commit()

    def highestmodseq_callback(self, crispin_client, new_uids,
                               updated_uids):
        uid_download_stack = uid_list_to_stack(new_uids)
        self.download_uids(crispin_client, uid_download_stack)

    def __check_flags(self, crispin_client, db_session, local_uids):
        """ Update message flags if folder has changed on the remote.

        If we have saved validity info for this folder, make sure the folder
        hasn't changed since we saved it. Otherwise we need to query for flag
        changes too.
        """
        saved_folder_info = common.get_folder_info(self.account_id,
                                                   db_session,
                                                   self.folder_name)
        if saved_folder_info is not None:
            last_highestmodseq = saved_folder_info.highestmodseq
            if last_highestmodseq > crispin_client.selected_highestmodseq:
                uids = crispin_client.new_and_updated_uids(last_highestmodseq)
                if uids:
                    _, updated = new_or_updated(uids, local_uids)
                    self.update_metadata(crispin_client, updated)
