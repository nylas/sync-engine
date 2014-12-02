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

from gevent import spawn, sleep
from gevent.coros import BoundedSemaphore
from sqlalchemy.orm import joinedload, load_only
from sqlalchemy.orm.exc import NoResultFound

from inbox.util.itert import chunk, partition

from inbox.crispin import GmailSettingError
from inbox.log import get_logger
from inbox.models import Message, Folder, Thread, Namespace, Account
from inbox.models.backends.gmail import GmailAccount
from inbox.models.backends.imap import ImapFolderInfo, ImapUid, ImapThread
from inbox.mailsync.backends.base import (create_db_objects,
                                          commit_uids,
                                          MailsyncError,
                                          mailsync_session_scope,
                                          thread_polling, thread_finished,
                                          THROTTLE_WAIT)
from inbox.mailsync.backends.imap.generic import (
    _pool, uidvalidity_cb, safe_download, report_progress, UIDStack)
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

    def sync(self):
        sync_folder_names_ids = self.prepare_sync()
        thread_download_lock = BoundedSemaphore(1)
        for folder_name, folder_id in sync_folder_names_ids:
            log.info('initializing folder sync')
            thread = GmailFolderSyncEngine(thread_download_lock,
                                           self.account_id, folder_name,
                                           folder_id,
                                           self.email_address,
                                           self.provider_name,
                                           self.poll_frequency,
                                           self.syncmanager_lock,
                                           self.refresh_flags_max,
                                           self.retry_fail_classes)
            thread.start()
            self.folder_monitors.add(thread)
            if thread.should_block:
                while not thread_polling(thread) and \
                        not thread_finished(thread) and \
                        not thread.ready():
                    sleep(self.heartbeat)

            # Allow individual folder sync monitors to shut themselves down
            # after completing the initial sync.
            if thread_finished(thread) or thread.ready():
                log.info('folder sync finished/killed',
                         folder_name=thread.folder_name)
                # NOTE: Greenlet is automatically removed from the group.

        self.folder_monitors.join()

GMessage = namedtuple('GMessage', 'uid g_metadata flags labels throttled')
log = get_logger()


class GmailFolderSyncEngine(CondstoreFolderSyncEngine):
    def __init__(self, thread_download_lock, *args, **kwargs):
        self.thread_download_lock = thread_download_lock
        CondstoreFolderSyncEngine.__init__(self, *args, **kwargs)

    @property
    def should_block(self):
        """Whether to wait for this folder sync to enter the polling state
        before starting others. Used so we can do initial Inbox and All Mail
        syncs in parallel."""
        with _pool(self.account_id).get() as crispin_client:
            return not self.is_inbox(crispin_client)

    def is_inbox(self, crispin_client):
        return self.folder_name == crispin_client.folder_names()['inbox']

    def is_all_mail(self, crispin_client):
        return self.folder_name == crispin_client.folder_names()['all']

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
                    deleted_uids = self.remove_deleted_uids(
                        db_session, local_uids, remote_uids)

                    local_uids = set(local_uids) - deleted_uids
                    unknown_uids = set(remote_uids) - local_uids
                    self.update_uid_counts(
                        db_session, remote_uid_count=remote_uid_count,
                        download_uid_count=len(unknown_uids))

            remote_g_metadata = crispin_client.g_metadata(unknown_uids)
            download_stack = UIDStack()
            change_poller = spawn(self.poll_for_changes, download_stack)
            if self.folder_name in uid_download_folders(crispin_client):
                full_download = self.__deduplicate_message_download(
                    crispin_client, remote_g_metadata, unknown_uids)
                for uid in sorted(full_download):
                    download_stack.put(uid, None)
                self.download_uids(crispin_client, download_stack)
            elif self.folder_name in thread_expand_folders(crispin_client):
                flags = crispin_client.flags(unknown_uids)
                for uid in sorted(unknown_uids):
                    if uid in flags:
                        gmessage = GMessage(uid, remote_g_metadata[uid],
                                            flags[uid].flags,
                                            flags[uid].labels,
                                            throttled=self.throttled)
                        download_stack.put(uid, gmessage)
                # We always download threads via the 'All Mail' folder.
                crispin_client.select_folder(
                    crispin_client.folder_names()['all'], uidvalidity_cb)
                self.__download_queued_threads(crispin_client, download_stack)
            else:
                raise MailsyncError(
                    'Unknown Gmail sync folder: {}'.format(self.folder_name))
        finally:
            if change_poller is not None:
                change_poller.kill()

    def poll_impl(self):
        should_idle = False
        with self.conn_pool.get() as crispin_client:
            crispin_client.select_folder(self.folder_name, uidvalidity_cb)
            download_stack = UIDStack()
            self.check_uid_changes(crispin_client, download_stack,
                                   async_download=False)
            if self.is_inbox(crispin_client):
                # Only idle on the inbox folder
                should_idle = True
                self.idle_wait(crispin_client)
        # Relinquish Crispin connection before sleeping.
        if not should_idle:
            sleep(self.poll_frequency)

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

        if self.folder_name in thread_expand_folders(crispin_client):
            flags = crispin_client.flags(to_download)
            for uid in sorted(to_download):
                if uid in flags and uid in g_metadata:
                    # IMAP will just return no data for a UID if it's
                    # disappeared from the folder in the meantime.
                    download_stack.put(uid, GMessage(uid, g_metadata[uid],
                                                     flags[uid].flags,
                                                     flags[uid].labels, False))
            if not async_download:
                # Need to select All Mail before doing thread expansion
                if not self.is_all_mail(crispin_client):
                    crispin_client.select_folder(
                        crispin_client.folder_names()['all'], uidvalidity_cb)
                self.__download_queued_threads(crispin_client, download_stack)
                if not self.is_all_mail(crispin_client):
                    crispin_client.select_folder(self.folder_name,
                                                 uidvalidity_cb)
        elif self.folder_name in uid_download_folders(crispin_client):
            for uid in sorted(to_download):
                download_stack.put(uid, None)
            if not async_download:
                self.download_uids(crispin_client, download_stack)
        else:
            raise MailsyncError(
                'Unknown Gmail sync folder: {}'.format(self.folder_name))

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
        return len(new_imapuids)

    def __download_queued_threads(self, all_mail_crispin_client,
                                  download_stack):
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
            self.sync_status.publish()
            _, message = download_stack.get()
            # Don't try to re-download any messages that are in the same
            # thread. (Putting this _before_ the download to guarantee no
            # context switches happen in the meantime; we _should_
            # re-download if another message arrives on the thread.)
            msgs_to_process = [m for _, m in download_stack if
                               m.g_metadata.thrid ==
                               message.g_metadata.thrid]
            msgs_to_process.append(message)
            download_stack.discard([
                item for item in download_stack if
                item[1].g_metadata.thrid == message.g_metadata.thrid])
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
            if self.is_inbox(all_mail_crispin_client):
                with self.syncmanager_lock:
                    # Since we download msgs from All Mail, we need to
                    # separately make sure we have ImapUids recorded for this
                    # folder (used in progress tracking, queuing, and delete
                    # detection).
                    log.debug('adding imapuid rows',
                              count=len(msgs_to_process))
                    with mailsync_session_scope() as db_session:
                        acc = db_session.query(GmailAccount).get(
                            self.account_id)
                        for msg in msgs_to_process:
                            add_new_imapuid(db_session, msg, self.folder_name,
                                            acc)

            report_progress(self.account_id, self.folder_name,
                            len(msgs_to_process),
                            download_stack.qsize())
            if self.throttled and message.throttled:
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
        with self.thread_download_lock:
            log.debug('downloading thread',
                      g_thrid=g_thrid, message_count=len(thread_uids))
            to_download = self.__deduplicate_message_download(
                crispin_client, thread_g_metadata, thread_uids)
            log.debug(deduplicated_message_count=len(to_download))
            for uids in chunk(to_download, crispin_client.CHUNK_SIZE):
                self.download_and_commit_uids(
                    crispin_client, crispin_client.selected_folder_name, uids)
        return len(to_download)


def uid_download_folders(crispin_client):
    """ Folders that don't get thread-expanded. """
    return [crispin_client.folder_names()[tag] for tag in
            ('trash', 'spam') if tag in crispin_client.folder_names()]


def thread_expand_folders(crispin_client):
    """Folders that *do* get thread-expanded. """
    return [crispin_client.folder_names()[tag] for tag in ('inbox', 'all')]


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
        new_imapuid.g_labels = [label for label in gmessage.labels]
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
                        msg_uid=uid, message=message_for[uid]) for uid in uids
                        if uid in message_for]
                    for item in new_imapuids:
                        # skip uids which have disappeared in the meantime
                        if item.msg_uid in flags:
                            item.update_imap_flags(flags[item.msg_uid].flags,
                                                   flags[item.msg_uid].labels)
                db_session.add_all(new_imapuids)
                db_session.commit()
