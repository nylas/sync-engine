"""
-----------------
GMAIL SYNC ENGINE
-----------------

Gmail is theoretically an IMAP backend, but it differs enough from standard
IMAP that we handle it differently. The state-machine rigamarole noted in
.imap.py applies, but we change a lot of the internal algorithms to fit Gmail's
structure.

Gmail has server-side threading, labels, and all messages are a subset of the
'All Mail' folder.

The only way to delete messages permanently on Gmail is to move a message to
the trash folder and then EXPUNGE.

We use Gmail's thread IDs locally, and download all mail via the All Mail
folder. We expand threads when downloading folders other than All Mail so the
user always gets the full thread when they look at mail.

"""
from __future__ import division

import os

from collections import namedtuple

from gevent import spawn
from gevent.queue import LifoQueue

from sqlalchemy.orm.exc import NoResultFound

from inbox.util.itert import chunk, partition
from inbox.util.cache import set_cache, get_cache, rm_cache
from inbox.util.misc import or_none

from inbox.crispin import GMetadata, connection_pool, GmailSettingError
from inbox.log import get_logger
from inbox.models.util import reconcile_message
from inbox.models import Message, Folder, Thread, Namespace
from inbox.models.backends.gmail import GmailAccount
from inbox.models.backends.imap import ImapUid, ImapThread
from inbox.mailsync.backends.base import (create_db_objects,
                                          commit_uids, new_or_updated,
                                          MailsyncError,
                                          mailsync_session_scope)
from inbox.mailsync.backends.imap.generic import (
    uidvalidity_cb, safe_download, add_uids_to_stack, uid_list_to_stack,
    report_progress)
from inbox.mailsync.backends.imap.condstore import CondstoreFolderSyncEngine
from inbox.mailsync.backends.imap.monitor import ImapSyncMonitor
from inbox.mailsync.backends.imap import common

PROVIDER = 'gmail'
SYNC_MONITOR_CLS = 'GmailSyncMonitor'


class GmailSyncMonitor(ImapSyncMonitor):
    def __init__(self, *args, **kwargs):
        kwargs['retry_fail_classes'] = [GmailSettingError]
        ImapSyncMonitor.__init__(self, *args, **kwargs)
        self.sync_engine_class = GmailFolderSyncEngine

GMessage = namedtuple('GMessage', 'uid g_metadata flags labels')
log = get_logger()


class GmailFolderSyncEngine(CondstoreFolderSyncEngine):
    def initial_sync_impl(self, crispin_client, local_uids,
                          uid_download_stack):
        # We wrap the block in a try/finally because the greenlets like
        # new_uid_poller need to be killed when this greenlet is interrupted
        new_uid_poller = None
        try:
            remote_uid_count = len(set(crispin_client.all_uids()))
            remote_g_metadata, update_uid_count = self.__fetch_g_metadata(
                crispin_client, local_uids)
            remote_uids = sorted(remote_g_metadata.keys(), key=int)
            log.info(remote_uid_count=len(remote_uids))
            if self.folder_name == crispin_client.folder_names()['all']:
                log.info(local_uid_count=len(local_uids))

            with self.syncmanager_lock:
                log.debug('gmail_initial_sync grabbed syncmanager_lock')
                with mailsync_session_scope() as db_session:
                    deleted_uids = self.remove_deleted_uids(
                        db_session, local_uids, remote_uids)
                    delete_uid_count = len(deleted_uids)

                    local_uids = set(local_uids) - deleted_uids
                    unknown_uids = set(remote_uids) - local_uids

                    # Persist the num(messages) to sync (any type of sync:
                    # download, update or delete) before we start.  Note that
                    # num_local_deleted, num_local_updated ARE the numbers to
                    # delete/update too since we make those changes rightaway
                    # before we start downloading messages.
                    self.update_uid_counts(
                        db_session, remote_uid_count=remote_uid_count,
                        download_uid_count=len(unknown_uids),
                        update_uid_count=update_uid_count,
                        delete_uid_count=delete_uid_count)

            if self.folder_name == crispin_client.folder_names()['inbox']:
                # We don't do an initial dedupe for Inbox because we do thread
                # expansion, which means even if we have a given msgid
                # downloaded, we miiight not have the whole thread. This means
                # that restarts cause duplicate work, but hopefully these
                # folders aren't too huge.
                message_download_stack = LifoQueue()
                flags = crispin_client.flags(unknown_uids)
                for uid in unknown_uids:
                    if uid in flags:
                        message_download_stack.put(
                            GMessage(uid, remote_g_metadata[uid],
                                     flags[uid].flags, flags[uid].labels))
                new_uid_poller = spawn(self.__check_new_g_thrids,
                                       message_download_stack)
                self.__download_queued_threads(crispin_client,
                                               message_download_stack)
            elif self.folder_name in uid_download_folders(crispin_client):
                full_download = self.__deduplicate_message_download(
                    crispin_client, remote_g_metadata, unknown_uids)
                add_uids_to_stack(full_download, uid_download_stack)
                new_uid_poller = spawn(self.check_new_uids, uid_download_stack)
                self.download_uids(crispin_client, uid_download_stack)
            else:
                raise MailsyncError(
                    'Unknown Gmail sync folder: {}'.format(self.folder_name))

            # Complete X-GM-MSGID mapping is no longer needed after initial
            # sync.
            rm_cache(remote_g_metadata_cache_file(self.account_id,
                                                  self.folder_name))
        finally:
            if new_uid_poller is not None:
                new_uid_poller.kill()

    def highestmodseq_callback(self, crispin_client, new_uids, updated_uids):
        uids = new_uids + updated_uids
        g_metadata = crispin_client.g_metadata(uids)
        to_download = self.__deduplicate_message_download(
            crispin_client, g_metadata, uids)

        if self.folder_name == crispin_client.folder_names()['inbox']:
            flags = crispin_client.flags(to_download)
            message_download_stack = LifoQueue()
            for uid in to_download:
                if uid in flags and uid in g_metadata:
                    # IMAP will just return no data for a UID if it's
                    # disappeared from the folder in the meantime.
                    message_download_stack.put(GMessage(
                        uid, g_metadata[uid], flags[uid].flags,
                        flags[uid].labels))
            self.__download_queued_threads(crispin_client,
                                           message_download_stack)
        elif self.folder_name in uid_download_folders(crispin_client):
            uid_download_stack = uid_list_to_stack(to_download)
            self.download_uids(crispin_client, uid_download_stack)
        else:
            raise MailsyncError(
                'Unknown Gmail sync folder: {}'.format(self.folder_name))

    def __fetch_g_metadata(self, crispin_client, uids):
        assert self.folder_name == crispin_client.selected_folder_name, \
            "crispin selected folder isn't as expected"
        remote_g_metadata = None
        update_uid_count = 0

        with mailsync_session_scope() as db_session:
            saved_folder_info = common.get_folder_info(
                self.account_id, db_session, self.folder_name)
            saved_highestmodseq = or_none(saved_folder_info, lambda i:
                                          i.highestmodseq)
        if saved_highestmodseq is not None:
            # If there's no cached validity we probably haven't run before.
            remote_g_metadata, update_uid_count = \
                self.__retrieve_saved_g_metadata(crispin_client, uids,
                                                 saved_highestmodseq)

        if remote_g_metadata is None:
            remote_g_metadata = crispin_client.g_metadata(
                crispin_client.all_uids())
            set_cache(remote_g_metadata_cache_file(self.account_id,
                                                   self.folder_name),
                      remote_g_metadata)
            # Save highestmodseq that corresponds to the saved g_metadata.
        with mailsync_session_scope() as db_session:
            common.update_folder_info(self.account_id, db_session,
                                      self.folder_name,
                                      crispin_client.selected_uidvalidity,
                                      crispin_client.selected_highestmodseq)
            db_session.commit()

        return remote_g_metadata, update_uid_count

    def __check_new_g_thrids(self, message_download_stack):
        """
        Check for new X-GM-THRIDs and add them to the download stack.

        We do this by comparing local UID lists to remote UID lists,
        maintaining the invariant that (stack uids)+(local uids) == (remote
        uids).

        We also remove local messages that have disappeared from the remote,
        since it's totally probable that users will be archiving mail as the
        initial sync goes on.

        We grab a new IMAP connection from the pool for this to isolate its
        actions from whatever the main greenlet may be doing.

        Runs until killed. (Intended to be run in a greenlet.)

        """
        with connection_pool(self.account_id).get() as crispin_client:
            crispin_client.select_folder(self.folder_name,
                                         uidvalidity_cb(self.account_id))
            while True:
                log.info('Checking for new/deleted messages during initial '
                         'sync.')
                remote_uids = set(crispin_client.all_uids())
                # We lock this section to make sure no messages are being
                # modified in the database while we make sure the queue is in a
                # good state.
                with self.syncmanager_lock:
                    with mailsync_session_scope() as db_session:
                        local_uids = common.all_uids(self.account_id,
                                                     db_session,
                                                     self.folder_name)
                        stack_uids = {gm.uid for gm in
                                      message_download_stack.queue}
                        local_with_pending_uids = local_uids | stack_uids
                        deleted_uids = self.remove_deleted_uids(
                            db_session, local_uids, remote_uids)
                        log.info(deleted_uid_count=len(deleted_uids))

                    # filter out messages that have disappeared on the remote
                    # side
                    new_message_download_stack = [gm for gm in
                                                  message_download_stack.queue
                                                  if gm.uid in remote_uids]

                    # add in any new uids from the remote
                    new_uids = [uid for uid in remote_uids if uid not in
                                local_with_pending_uids]
                    flags = crispin_client.flags(new_uids)
                    g_metadata = crispin_client.g_metadata(new_uids)
                    log.info('adding new messages to download queue',
                             count=min(len(flags), len(g_metadata)))
                    for new_uid in new_uids:
                        # could have disappeared from the folder in the
                        # meantime
                        if new_uid in flags and new_uid in g_metadata:
                            new_message_download_stack.append(
                                GMessage(new_uid, g_metadata[new_uid],
                                         flags[new_uid].flags,
                                         flags[new_uid].labels))
                    message_download_stack.queue = sorted(
                        new_message_download_stack, key=lambda m: m.uid)

                    with mailsync_session_scope() as db_session:
                        self.update_uid_counts(
                            db_session,
                            remote_uid_count=len(remote_uids),
                            download_uid_count=message_download_stack.qsize(),
                            delete_uid_count=len(deleted_uids))

                log.info('idling', timeout=self.poll_frequency)
                crispin_client.conn.idle()
                crispin_client.conn.idle_check(timeout=self.poll_frequency)
                crispin_client.conn.idle_done()
                log.info('IDLE detected changes or timeout reached')

    def __deduplicate_message_download(self, crispin_client, remote_g_metadata,
                                       uids):
        """
        Deduplicate message download using X-GM-MSGID.

        Returns
        -------
        list
            Deduplicated UIDs.

        """
        with mailsync_session_scope() as db_session:
            local_g_msgids = g_msgids(self.account_id, db_session,
                                      in_={remote_g_metadata[uid].msgid
                                           for uid in uids if uid in
                                           remote_g_metadata})

        full_download, imapuid_only = partition(
            lambda uid: uid in remote_g_metadata and
            remote_g_metadata[uid].msgid in local_g_msgids,
            sorted(uids, key=int))
        if imapuid_only:
            log.info('skipping already downloaded uids',
                     count=len(imapuid_only))
            # Since we always download messages via All Mail and create the
            # relevant All Mail ImapUids too at that time, we don't need to
            # create them again here if we're deduping All Mail downloads.
            if crispin_client.selected_folder_name != \
                    crispin_client.folder_names()['all']:
                add_new_imapuids(crispin_client, remote_g_metadata,
                                 self.syncmanager_lock, imapuid_only)

        return full_download

    def __deduplicate_message_object_creation(self, db_session, raw_messages):
        new_g_msgids = {msg.g_msgid for msg in raw_messages}
        existing_g_msgids = g_msgids(self.account_id, db_session,
                                     in_=new_g_msgids)
        return [msg for msg in raw_messages if msg.g_msgid not in
                existing_g_msgids]

    def add_message_attrs(self, db_session, new_uid, msg, folder):
        """ Gmail-specific post-create-message bits. """
        # Disable autoflush so we don't try to flush a message with null
        # thread_id, causing a crash, and so that we don't flush on each
        # added/removed label.
        with db_session.no_autoflush:
            new_uid.message.g_msgid = msg.g_msgid
            # NOTE: g_thrid == g_msgid on the first message in the thread :)
            new_uid.message.g_thrid = msg.g_thrid

            # we rely on Gmail's threading instead of our threading algorithm.
            new_uid.message.thread_order = 0
            new_uid.update_imap_flags(msg.flags, msg.g_labels)

            thread = new_uid.message.thread = ImapThread.from_gmail_message(
                db_session, new_uid.account.namespace, new_uid.message)

            # make sure this thread has all the correct labels
            new_labels = common.update_thread_labels(thread, folder.name,
                                                     msg.g_labels, db_session)

            # Reconciliation for Drafts, Sent Mail folders:
            if (('draft' in new_labels or 'sent' in new_labels) and not
                    msg.created and new_uid.message.inbox_uid):
                reconcile_message(db_session, new_uid.message.inbox_uid,
                                  new_uid.message)

            return new_uid

    def download_and_commit_uids(self, crispin_client, folder_name, uids):
        log.info('downloading uids', uids=uids)
        raw_messages = safe_download(crispin_client, uids)
        with self.syncmanager_lock:
            # there is the possibility that another green thread has already
            # downloaded some message(s) from this batch... check within the
            # lock
            with mailsync_session_scope() as db_session:
                raw_messages = self.__deduplicate_message_object_creation(
                    db_session, raw_messages)
                if not raw_messages:
                    return 0
                new_imapuids = create_db_objects(
                    self.account_id, db_session, log, folder_name,
                    raw_messages, self.create_message)
                commit_uids(db_session, log, new_imapuids)
                log.info(new_committed_message_count=len(new_imapuids))
        return len(new_imapuids)

    def __download_queued_threads(self, crispin_client,
                                  message_download_stack):
        """
        Download threads until `message_download_stack` is empty.

        UIDs and g_metadata that come out of `message_download_stack` are for
        the _folder that threads are being expanded in_.

        Threads are downloaded in the order they come out of the stack, which
        _ought_ to be putting newest threads at the top. Messages are
        downloaded newest-to-oldest in thread. (Threads are expanded to all
        messages in the email archive that belong to the threads corresponding
        to the given uids.)

        """
        num_total_messages = message_download_stack.qsize()
        log.info(num_total_messages=num_total_messages)

        log.info('Expanding threads and downloading messages.')
        # We still need the original crispin connection for progress reporting,
        # so the easiest thing to do here with the current pooling setup is to
        # create a new crispin client for querying All Mail.
        with connection_pool(self.account_id).get() as all_mail_crispin_client:
            all_mail_crispin_client.select_folder(
                crispin_client.folder_names()['all'],
                uidvalidity_cb(self.account_id))

            # Since we do thread expansion, for any given thread, even if we
            # already have the UID in the given GMessage downloaded, we may not
            # have _every_ message in the thread. We have to expand it and make
            # sure we have all messages.
            while not message_download_stack.empty():
                message = message_download_stack.get_nowait()
                # Don't try to re-download any messages that are in the same
                # thread. (Putting this _before_ the download to guarantee no
                # context switches happen in the meantime; we _should_
                # re-download if another message arrives on the thread.)
                processed_msgs = [m for m in message_download_stack.queue if
                                  m.g_metadata.thrid ==
                                  message.g_metadata.thrid]
                processed_msgs.append(message)
                message_download_stack.queue = [
                    m for m in message_download_stack.queue if
                    m.g_metadata.thrid != message.g_metadata.thrid]
                thread_uids = all_mail_crispin_client.expand_thread(
                    message.g_metadata.thrid)
                thread_g_metadata = all_mail_crispin_client.g_metadata(
                    thread_uids)
                self.__download_thread(all_mail_crispin_client,
                                       thread_g_metadata,
                                       message.g_metadata.thrid, thread_uids)
                # In theory we only ever have one Greenlet modifying ImapUid
                # entries for a non-All Mail folder, but grab the lock anyway
                # to be safe.
                with self.syncmanager_lock:
                    # Since we download msgs from All Mail, we need to
                    # separately make sure we have ImapUids recorded for this
                    # folder (used in progress tracking, queuing, and delete
                    # detection).
                    log.debug('adding imapuid rows', count=len(processed_msgs))
                    with mailsync_session_scope() as db_session:
                        acc = db_session.query(GmailAccount).get(
                            crispin_client.account_id)
                        for msg in processed_msgs:
                            add_new_imapuid(db_session, msg, self.folder_name,
                                            acc)

                report_progress(self.account_id, self.folder_name,
                                len(processed_msgs),
                                message_download_stack.qsize())
            log.info('Message download queue emptied')
        # Intentionally don't report which UIDVALIDITY we've saved messages to
        # because we have All Mail selected and don't have the UIDVALIDITY for
        # the folder we're actually downloading messages for.

    def __download_thread(self, crispin_client, thread_g_metadata, g_thrid,
                          thread_uids):
        """
        Download all messages in thread identified by `g_thrid`.

        Messages are downloaded most-recent-first via All Mail, which allows us
        to get the entire thread regardless of which folders it's in.
        """
        log.debug('downloading thread',
                  g_thrid=g_thrid, message_count=len(thread_uids))
        to_download = self.__deduplicate_message_download(
            crispin_client, thread_g_metadata, thread_uids)
        log.debug(deduplicated_message_count=len(to_download))
        for uids in chunk(reversed(to_download), crispin_client.CHUNK_SIZE):
            self.download_and_commit_uids(crispin_client,
                                          crispin_client.selected_folder_name,
                                          uids)
        return len(to_download)

    def __retrieve_saved_g_metadata(self, crispin_client, local_uids,
                                    saved_highestmodseq):
        log.info('Attempting to retrieve remote_g_metadata from cache')

        update_uid_count = 0
        remote_g_metadata = get_cache(remote_g_metadata_cache_file(
            crispin_client.account_id, self.folder_name))

        if remote_g_metadata is not None:
            # Rebuild namedtuples because msgpack
            remote_g_metadata = {k: GMetadata(*v) for k, v in
                                 remote_g_metadata.iteritems()}

            log.info('successfully retrieved remote_g_metadata cache',
                     object_count=len(remote_g_metadata))
            if crispin_client.selected_highestmodseq > saved_highestmodseq:
                update_uid_count = self.__update_saved_g_metadata(
                    crispin_client, remote_g_metadata, local_uids)
        else:
            log.info("No cached data found")
        return remote_g_metadata, update_uid_count

    def __update_saved_g_metadata(self, crispin_client, remote_g_metadata,
                                  local_uids):
        """
        If HIGHESTMODSEQ has changed since we saved the X-GM-MSGID cache,
        we need to query for any changes since then and update the saved
        data.

        """
        log.info('Updating cache with latest changes')
        # Any uids we don't already have will be downloaded correctly as usual,
        # but updated uids need to be updated manually.
        # XXX it may actually be faster to just query for X-GM-MSGID for the
        # whole folder rather than getting changed UIDs first; MODSEQ queries
        # are slow on large folders.
        modified = crispin_client.new_and_updated_uids(
            crispin_client.selected_highestmodseq)
        log.info(modified_msg_count=len(modified))
        new, updated = new_or_updated(modified, local_uids)
        log.info(new_uid_count=len(new), updated_uid_count=len(updated))
        if new:
            remote_g_metadata.update(crispin_client.g_metadata(new))
            log.info('Updated cache with new messages')
        else:
            log.info('No new messages to update metadata for')
        # Filter out messages that have disappeared.
        old_len = len(remote_g_metadata)
        current_remote_uids = set(crispin_client.all_uids())
        remote_g_metadata = dict((uid, md) for uid, md in
                                 remote_g_metadata.iteritems() if uid in
                                 current_remote_uids)
        num_removed = old_len - len(remote_g_metadata)
        if num_removed > 0:
            log.info(removed_msg_count=num_removed)
        set_cache(remote_g_metadata_cache_file(self.account_id,
                                               self.folder_name),
                  remote_g_metadata)
        if updated:
            # It's easy and fast to just update these here and now.
            # Bigger chunk because the data being fetched here is very small.
            for uids in chunk(updated, 5 * crispin_client.CHUNK_SIZE):
                self.update_metadata(crispin_client, uids)
            log.info('updated metadata for modified messages',
                     msg_count=len(updated))
            return len(updated)
        else:
            log.info('No modified messages to update metadata for')
            return 0


def uid_download_folders(crispin_client):
    """ Folders that don't get thread-expanded. """
    return [crispin_client.folder_names()[tag] for tag in
            ('trash', 'spam', 'all') if tag in crispin_client.folder_names()]


def g_msgids(account_id, session, in_):
    if not in_:
        return []
    # Easiest way to account-filter Messages is to namespace-filter from
    # the associated thread. (Messages may not necessarily have associated
    # ImapUids.)
    in_ = {long(i) for i in in_}  # in case they are strings
    if len(in_) > 1000:
        # If in_ is really large, passing all the values to MySQL can get
        # deadly slow. (Approximate threshold empirically determined)
        query = session.query(Message.g_msgid).join(Thread).join(Namespace). \
            filter(Namespace.account_id == account_id).all()
        return sorted(g_msgid for g_msgid, in query if g_msgid in in_)
    # But in the normal case that in_ only has a few elements, it's way better
    # to not fetch a bunch of values from MySQL only to return a few of them.
    query = session.query(Message.g_msgid).join(Thread).join(Namespace). \
        filter(Namespace.account_id == account_id,
               Message.g_msgid.in_(in_)).all()
    return {g_msgid for g_msgid, in query}


def g_metadata(account_id, session, folder_name):
    query = session.query(ImapUid.msg_uid, Message.g_msgid, Message.g_thrid)\
        .filter(ImapUid.account_id == account_id,
                Folder.name == folder_name,
                ImapUid.message_id == Message.id)

    return dict([(uid, dict(msgid=g_msgid, thrid=g_thrid))
                 for uid, g_msgid, g_thrid in query])


def remote_g_metadata_cache_file(account_id, folder_name):
    return os.path.join(str(account_id), folder_name, 'remote_g_metadata')


def add_new_imapuid(db_session, gmessage, folder_name, acc):
    """
    Add ImapUid object for this GMessage if we don't already have one.

    Parameters
    ----------
    message : GMessage
        Message to add ImapUid for.
    folder_name : str
        Which folder to add the ImapUid in.
    acc : GmailAccount
        Which account to associate the message with. (Not looking this up
        within this function is a db access optimization.)

    """
    if not db_session.query(ImapUid.msg_uid).join(Folder).filter(
            Folder.name == folder_name,
            ImapUid.account_id == acc.id,
            ImapUid.msg_uid == gmessage.uid).all():
        try:
            message = db_session.query(Message).join(ImapThread).filter(
                ImapThread.g_thrid == gmessage.g_metadata.thrid,
                Message.g_thrid == gmessage.g_metadata.thrid,
                Message.g_msgid == gmessage.g_metadata.msgid,
                ImapThread.namespace_id == acc.namespace.id).one()
        except NoResultFound:
            # this may occur when a thread is expanded and those messages are
            # downloaded and committed, then new messages on that thread arrive
            # and get added to the download queue before this code is run
            log.debug('no Message object found, skipping imapuid creation',
                      uid=gmessage.uid, g_msgid=gmessage.g_metadata.msgid)
            return
        new_imapuid = ImapUid(
            account=acc,
            folder=Folder.find_or_create(db_session, acc, folder_name),
            msg_uid=gmessage.uid, message=message)
        new_imapuid.update_imap_flags(gmessage.flags, gmessage.labels)
        db_session.add(new_imapuid)
        db_session.commit()
    else:
        log.debug('skipping imapuid creation',
                  uid=gmessage.uid, g_msgid=gmessage.g_metadata.msgid)


def add_new_imapuids(crispin_client, remote_g_metadata, syncmanager_lock,
                     uids):
    """
    Add ImapUid entries only for (already-downloaded) messages.

    If a message has already been downloaded via another folder, we only need
    to add `ImapUid` accounting for the current folder. `Message` objects
    etc. have already been created.

    """
    flags = crispin_client.flags(uids)

    with syncmanager_lock:
        with mailsync_session_scope() as db_session:
            # Since we prioritize download for messages in certain threads, we
            # may already have ImapUid entries despite calling this method.
            local_folder_uids = {uid for uid, in
                                 db_session.query(ImapUid.msg_uid).join(Folder)
                                 .filter(
                                     ImapUid.account_id ==
                                     crispin_client.account_id,
                                     Folder.name ==
                                     crispin_client.selected_folder_name,
                                     ImapUid.msg_uid.in_(uids))}
            uids = [uid for uid in uids if uid not in local_folder_uids]

            if uids:
                acc = db_session.query(GmailAccount).get(
                    crispin_client.account_id)

                # collate message objects to relate the new imapuids to
                imapuid_for = dict([(metadata.msgid, uid) for (uid, metadata)
                                    in remote_g_metadata.items()
                                    if uid in uids])
                imapuid_g_msgids = [remote_g_metadata[uid].msgid for uid in
                                    uids]
                message_for = dict([(imapuid_for[m.g_msgid], m) for m in
                                    db_session.query(Message).join(ImapThread)
                                    .filter(
                                        Message.g_msgid.in_(imapuid_g_msgids),
                                        ImapThread.namespace_id ==
                                        acc.namespace.id)])

                # Stop Folder.find_or_create()'s query from triggering a flush.
                with db_session.no_autoflush:
                    new_imapuids = [ImapUid(
                        account=acc,
                        folder=Folder.find_or_create(
                            db_session, acc,
                            crispin_client.selected_folder_name),
                        msg_uid=uid, message=message_for[uid]) for uid in uids]
                    for item in new_imapuids:
                        # skip uids which have disappeared in the meantime
                        if item.msg_uid in flags:
                            item.update_imap_flags(flags[item.msg_uid].flags,
                                                   flags[item.msg_uid].labels)
                db_session.add_all(new_imapuids)
                db_session.commit()
