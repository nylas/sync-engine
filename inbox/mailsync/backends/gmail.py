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
from collections import namedtuple
from gevent import spawn, sleep
from sqlalchemy.orm import joinedload, load_only

from inbox.util.itert import chunk, partition

from inbox.crispin import GmailSettingError
from inbox.log import get_logger
from inbox.models import Message, Folder, Namespace, Account
from inbox.models.backends.gmail import GmailAccount
from inbox.models.backends.imap import ImapFolderInfo, ImapUid, ImapThread
from inbox.mailsync.backends.base import (create_db_objects,
                                          commit_uids,
                                          mailsync_session_scope,
                                          THROTTLE_WAIT)
from inbox.mailsync.backends.imap.generic import safe_download, UIDStack
from inbox.mailsync.backends.imap.condstore import CondstoreFolderSyncEngine
from inbox.mailsync.backends.imap.monitor import ImapSyncMonitor
from inbox.mailsync.backends.imap import common

PROVIDER = 'gmail'
SYNC_MONITOR_CLS = 'GmailSyncMonitor'

GMetadata = namedtuple('GMetadata', 'msgid thrid throttled')


class GmailSyncMonitor(ImapSyncMonitor):
    def __init__(self, *args, **kwargs):
        kwargs['retry_fail_classes'] = [GmailSettingError]
        ImapSyncMonitor.__init__(self, *args, **kwargs)
        self.sync_engine_class = GmailFolderSyncEngine

    def sync(self):
        self.start_new_folder_sync_engines(set())
        self.folder_monitors.join()

log = get_logger()


class GmailFolderSyncEngine(CondstoreFolderSyncEngine):
    def __init__(self, *args, **kwargs):
        CondstoreFolderSyncEngine.__init__(self, *args, **kwargs)
        self.saved_uids = set()

    def is_all_mail(self, crispin_client):
        return self.folder_name == crispin_client.folder_names()['all']

    def should_idle(self, crispin_client):
        return self.is_all_mail(crispin_client)

    def initial_sync_impl(self, crispin_client):
        # We wrap the block in a try/finally because the greenlets like
        # change_poller need to be killed when this greenlet is interrupted
        change_poller = None
        try:
            with mailsync_session_scope() as db_session:
                local_uids = common.all_uids(self.account_id, db_session,
                                             self.folder_name)
            remote_uids = sorted(crispin_client.all_uids(), key=int)
            remote_uid_count = len(remote_uids)
            with self.syncmanager_lock:
                with mailsync_session_scope() as db_session:
                    self.remove_deleted_uids(db_session, local_uids,
                                             remote_uids)
                    unknown_uids = set(remote_uids) - local_uids
                    self.update_uid_counts(
                        db_session, remote_uid_count=remote_uid_count,
                        download_uid_count=len(unknown_uids))

            remote_g_metadata = crispin_client.g_metadata(unknown_uids)
            download_stack = UIDStack()
            change_poller = spawn(self.poll_for_changes, download_stack)
            if self.is_all_mail(crispin_client):
                # Put UIDs on the stack such that UIDs for messages in the
                # inbox get downloaded first, and such that higher (i.e., more
                # recent) UIDs get downloaded before lower ones.
                inbox_uids = crispin_client.conn.search(['X-GM-LABELS inbox'])
                ordered_uids_to_sync = [u for u in sorted(remote_uids) if u not
                                        in inbox_uids] + sorted(inbox_uids)
                for uid in ordered_uids_to_sync:
                    if uid in remote_g_metadata:
                        metadata = GMetadata(remote_g_metadata[uid].msgid,
                                             remote_g_metadata[uid].thrid,
                                             self.throttled)
                        download_stack.put(uid, metadata)
                self.__download_queued_threads(crispin_client, download_stack)
            else:
                full_download = self.__deduplicate_message_download(
                    crispin_client, remote_g_metadata, unknown_uids)
                for uid in sorted(full_download):
                    download_stack.put(uid, None)
                self.download_uids(crispin_client, download_stack)
        finally:
            if change_poller is not None:
                change_poller.kill()

    def resync_uids_impl(self):
        with mailsync_session_scope() as db_session:
            imap_folder_info_entry = db_session.query(ImapFolderInfo)\
                .options(load_only('uidvalidity', 'highestmodseq'))\
                .filter_by(account_id=self.account_id,
                           folder_id=self.folder_id)\
                .one()
            with self.conn_pool.get() as crispin_client:
                crispin_client.select_folder(self.folder_name,
                                             lambda *args: True)
                uidvalidity = crispin_client.selected_uidvalidity
                if uidvalidity <= imap_folder_info_entry.uidvalidity:
                    # if the remote UIDVALIDITY is less than or equal to -
                    # from my (siro) understanding it should not be less than -
                    # the local UIDVALIDITY log a debug message and exit right
                    # away
                    log.debug('UIDVALIDITY unchanged')
                    return
                msg_uids = crispin_client.all_uids()
                mapping = {g_msgid: msg_uid for msg_uid, g_msgid in
                           crispin_client.g_msgids(msg_uids).iteritems()}
            imap_uid_entries = db_session.query(ImapUid)\
                .options(load_only('msg_uid'),
                         joinedload('message').load_only('g_msgid'))\
                .filter_by(account_id=self.account_id,
                           folder_id=self.folder_id)
            CHUNK_SIZE = 1000
            for entry in imap_uid_entries.yield_per(CHUNK_SIZE):
                if entry.message.g_msgid in mapping:
                    log.debug('X-GM-MSGID {} from UID {} to UID {}'.format(
                        entry.message.g_msgid,
                        entry.msg_uid,
                        mapping[entry.message.g_msgid]))
                    entry.msg_uid = mapping[entry.message.g_msgid]
                else:
                    db_session.delete(entry)
            log.debug('UIDVALIDITY from {} to {}'.format(
                imap_folder_info_entry.uidvalidity, uidvalidity))
            imap_folder_info_entry.uidvalidity = uidvalidity
            imap_folder_info_entry.highestmodseq = None
            db_session.commit()

    def highestmodseq_callback(self, crispin_client, new_uids, updated_uids,
                               download_stack, async_download):
        log.debug('running highestmodseq callback')
        uids = new_uids + updated_uids
        g_metadata = crispin_client.g_metadata(uids)
        to_download = self.__deduplicate_message_download(
            crispin_client, g_metadata, uids)
        if self.is_all_mail(crispin_client):
            for uid in sorted(to_download):
                # IMAP will just return no data for a UID if it's
                # disappeared from the folder in the meantime.
                if uid in g_metadata:
                    download_stack.put(
                        uid, GMetadata(False, g_metadata[uid].msgid,
                                       g_metadata[uid].thrid))
            if not async_download:
                self.__download_queued_threads(crispin_client, download_stack)
        else:
            for uid in sorted(to_download):
                download_stack.put(uid, None)
            if not async_download:
                self.download_uids(crispin_client, download_stack)

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

            # FIXME: @karim not sure if it's necessary to clean up strings like
            # \\Inbox, \\Trash, etc.
            new_uid.g_labels = [label for label in msg.g_labels]

            thread = new_uid.message.thread = ImapThread.from_gmail_message(
                db_session, new_uid.account.namespace, new_uid.message)

        # make sure this thread has all the correct labels
        common.add_any_new_thread_labels(thread, new_uid, db_session)
        return new_uid

    def download_and_commit_uids(self, crispin_client, folder_name, uids):
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
                commit_uids(db_session, new_imapuids, self.provider_name)
        self.saved_uids.update(uids)
        return len(new_imapuids)

    def __download_queued_threads(self, crispin_client, download_stack):
        """
        Download threads until `download_stack` is empty.

        UIDs and g_metadata that come out of `download_stack` are for
        the _folder that threads are being expanded in_.

        Threads are downloaded in the order they come out of the stack, which
        _ought_ to be putting newest threads at the top. Messages are
        downloaded oldest-to-newest in thread. (Threads are expanded to all
        messages in the email archive that belong to the threads corresponding
        to the given uids.)

        """
        num_total_messages = download_stack.qsize()
        log.info(num_total_messages=num_total_messages)

        log.info('Expanding threads and downloading messages.')
        # Since we do thread expansion, for any given thread, even if we
        # already have the UID in the given GMessage downloaded, we may not
        # have _every_ message in the thread. We have to expand it and make
        # sure we have all messages.
        while not download_stack.empty():
            uid, metadata = download_stack.get()
            if uid in self.saved_uids:
                continue
            # TODO(emfree): a significantly higher-performing alternative would
            # be to maintain a complete metadata map `self.g_metadata` and just
            # reference it here.
            thread_uids = crispin_client.expand_thread(metadata.thrid)
            thread_g_metadata = crispin_client.g_metadata(thread_uids)
            self.__download_thread(crispin_client,
                                   thread_g_metadata,
                                   metadata.thrid, thread_uids)
            self.sync_status.publish()
            if self.throttled and metadata is not None and metadata.throttled:
                # Check to see if the account's throttled state has been
                # modified. If so, immediately accelerate.
                with mailsync_session_scope() as db_session:
                    acc = db_session.query(Account).get(self.account_id)
                    self.throttled = acc.throttled
                log.debug('throttled; sleeping')
                if self.throttled:
                    sleep(THROTTLE_WAIT)
        log.info('Message download queue emptied')
        # Intentionally don't report which UIDVALIDITY we've saved messages to
        # because we have All Mail selected and don't have the UIDVALIDITY for
        # the folder we're actually downloading messages for.

    def __download_thread(self, crispin_client, thread_g_metadata, g_thrid,
                          thread_uids):
        """
        Download all messages in thread identified by `g_thrid`.

        Messages are downloaded oldest-first via All Mail, which allows us
        to get the entire thread regardless of which folders it's in. We do
        oldest-first so that if the thread started with a message sent from the
        Inbox API, we can reconcile this thread appropriately with the existing
        message/thread.
        """
        log.debug('downloading thread',
                  g_thrid=g_thrid, message_count=len(thread_uids))
        to_download = self.__deduplicate_message_download(
            crispin_client, thread_g_metadata, thread_uids)
        log.debug(deduplicated_message_count=len(to_download))
        for uids in chunk(to_download, crispin_client.CHUNK_SIZE):
            self.download_and_commit_uids(
                crispin_client, crispin_client.selected_folder_name, uids)
        return len(to_download)


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
        query = session.query(Message.g_msgid).join(Namespace). \
            filter(Namespace.account_id == account_id).all()
        return sorted(g_msgid for g_msgid, in query if g_msgid in in_)
    # But in the normal case that in_ only has a few elements, it's way better
    # to not fetch a bunch of values from MySQL only to return a few of them.
    query = session.query(Message.g_msgid).join(Namespace). \
        filter(Namespace.account_id == account_id,
               Message.g_msgid.in_(in_)).all()
    return {g_msgid for g_msgid, in query}


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
                        msg_uid=uid, message=message_for[uid]) for uid in uids
                        if uid in message_for]
                    for item in new_imapuids:
                        # skip uids which have disappeared in the meantime
                        if item.msg_uid in flags:
                            item.update_imap_flags(flags[item.msg_uid].flags,
                                                   flags[item.msg_uid].labels)
                db_session.add_all(new_imapuids)
                db_session.commit()
