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
from collections import OrderedDict
from datetime import datetime, timedelta
from gevent import kill, spawn, sleep
from sqlalchemy.orm import joinedload, load_only

from inbox.util.itert import chunk
from inbox.util.debug import bind_context

from nylas.logging import get_logger
from inbox.models import Message, Folder, Namespace, Account, Label, Category
from inbox.models.backends.imap import ImapFolderInfo, ImapUid, ImapThread
from inbox.models.session import session_scope
from inbox.mailsync.backends.imap.generic import FolderSyncEngine
from inbox.mailsync.backends.imap.monitor import ImapSyncMonitor
from inbox.mailsync.backends.imap import common
from inbox.mailsync.gc import LabelRenameHandler
from inbox.mailsync.backends.base import THROTTLE_COUNT, THROTTLE_WAIT
log = get_logger()

PROVIDER = 'gmail'
SYNC_MONITOR_CLS = 'GmailSyncMonitor'


MAX_DOWNLOAD_BYTES = 2 ** 20
# USE MAX_DOWNLOAD_COUNT = 1 instead of 30 until N1 launch herding dies.
MAX_DOWNLOAD_COUNT = 1


class GmailSyncMonitor(ImapSyncMonitor):

    def __init__(self, *args, **kwargs):
        ImapSyncMonitor.__init__(self, *args, **kwargs)
        self.sync_engine_class = GmailFolderSyncEngine

    def save_folder_names(self, db_session, raw_folders):
        """
        Save the folders, labels present on the remote backend for an account.

        * Create Folder/ Label objects.
        * Delete Folders/ Labels that no longer exist on the remote.

        Notes
        -----
        Gmail uses IMAP folders and labels.
        Canonical folders ('all', 'trash', 'spam') are therefore mapped to both
        Folder and Label objects, everything else is created as a Label only.

        We don't canonicalize names to lowercase when saving because
        different backends may be case-sensitive or otherwise - code that
        references saved names should canonicalize if needed when doing
        comparisons.

        """
        account = db_session.query(Account).get(self.account_id)

        old_labels = {label for label in db_session.query(Label).filter(
            Label.account_id == self.account_id,
            Label.deleted_at == None)}

        current_labels = set()

        # Create new labels, folders
        for raw_folder in raw_folders:
            if raw_folder.role == 'starred':
                # The starred state of messages is tracked separately
                # (we set Message.is_starred from the '\\Flagged' flag)
                continue

            label = Label.find_or_create(db_session, account,
                                         raw_folder.display_name,
                                         raw_folder.role)
            current_labels.add(label)

            if label.deleted_at is not None:
                # This is a label which was previously marked as deleted
                # but which mysteriously reappeared. Unmark it.
                log.info('Deleted label recreated on remote',
                         name=raw_folder.display_name)
                label.deleted_at = None
                label.category.deleted_at = None

            if raw_folder.role in ('all', 'spam', 'trash'):
                folder = db_session.query(Folder).filter(
                    Folder.account_id == account.id,
                    Folder.canonical_name == raw_folder.role).first()
                if folder:
                    if folder.name != raw_folder.display_name:
                        log.info('Folder name changed on remote',
                                 account_id=self.account_id,
                                 role=raw_folder.role,
                                 new_name=raw_folder.display_name,
                                 name=folder.name)
                        folder.name = raw_folder.display_name

                    if folder.category:
                        if folder.category.display_name != \
                                raw_folder.display_name:
                            folder.category.display_name = raw_folder.display_name  # noqa
                    else:
                        log.info('Creating category for folder',
                                 account_id=self.account_id,
                                 folder_name=folder.name)
                        folder.category = Category.find_or_create(
                            db_session, namespace_id=account.namespace.id,
                            name=raw_folder.role,
                            display_name=raw_folder.display_name,
                            type_='folder')
                else:
                    Folder.find_or_create(db_session, account,
                                          raw_folder.display_name,
                                          raw_folder.role)

        # Ensure sync_should_run is True for the folders we want to sync (for
        # Gmail, that's just all folders, since we created them above if
        # they didn't exist.)
        for folder in account.folders:
            if folder.imapsyncstatus:
                folder.imapsyncstatus.sync_should_run = True

        # Go through the labels which have been "deleted" (i.e: they don't
        # show up when running LIST) and mark them as such.
        # We can't delete labels directly because Gmail allows users to hide
        # folders --- we need to check that there's no messages still
        # associated with the label.
        deleted_labels = old_labels - current_labels
        for deleted_label in deleted_labels:
            deleted_label.deleted_at = datetime.now()
            cat = deleted_label.category
            cat.deleted_at = datetime.now()

        new_labels = current_labels - old_labels
        for label in new_labels:
            rename_handler = LabelRenameHandler(
                account_id=self.account_id,
                namespace_id=self.namespace_id,
                label_name=label.name)

            rename_handler.start()

        db_session.commit()


class GmailFolderSyncEngine(FolderSyncEngine):

    def __init__(self, *args, **kwargs):
        FolderSyncEngine.__init__(self, *args, **kwargs)
        self.saved_uids = set()

    def is_all_mail(self, crispin_client):
        if not hasattr(self, '_is_all_mail'):
            self._is_all_mail = (self.folder_name in
                                 crispin_client.folder_names()['all'])
        return self._is_all_mail

    def should_idle(self, crispin_client):
        return self.is_all_mail(crispin_client)

    def initial_sync_impl(self, crispin_client):
        # We wrap the block in a try/finally because the greenlets like
        # change_poller need to be killed when this greenlet is interrupted
        change_poller = None
        try:
            remote_uids = sorted(crispin_client.all_uids(), key=int)
            with self.syncmanager_lock:
                with session_scope(self.namespace_id) as db_session:
                    local_uids = common.local_uids(self.account_id, db_session,
                                                   self.folder_id)
                    common.remove_deleted_uids(
                        self.account_id, self.folder_id,
                        set(local_uids) - set(remote_uids),
                        db_session)
                    unknown_uids = set(remote_uids) - local_uids
                    self.update_uid_counts(
                        db_session, remote_uid_count=len(remote_uids),
                        download_uid_count=len(unknown_uids))

            change_poller = spawn(self.poll_for_changes)
            bind_context(change_poller, 'changepoller', self.account_id,
                         self.folder_id)

            if self.is_all_mail(crispin_client):
                # Prioritize UIDs for messages in the inbox folder.
                if len(remote_uids) < 1e6:
                    inbox_uids = set(
                        crispin_client.search_uids(['X-GM-LABELS inbox']))
                else:
                    # The search above is really slow (times out) on really
                    # large mailboxes, so bound the search to messages within
                    # the past month in order to get anywhere.
                    since = (datetime.utcnow() - timedelta(days=30)). \
                        strftime('%d-%b-%Y')
                    inbox_uids = set(crispin_client.search_uids(
                        ['X-GM-LABELS inbox', 'SINCE {}'.format(since)]))
                uids_to_download = (sorted(unknown_uids - inbox_uids) +
                                    sorted(unknown_uids & inbox_uids))
            else:
                uids_to_download = sorted(unknown_uids)

            for uids in chunk(reversed(uids_to_download), 1024):
                g_metadata = crispin_client.g_metadata(uids)
                # UIDs might have been expunged since sync started, in which
                # case the g_metadata call above will return nothing.
                # They may also have been preemptively downloaded by thread
                # expansion. We can omit such UIDs.
                uids = [u for u in uids if u in g_metadata and u not in
                        self.saved_uids]
                self.batch_download_uids(crispin_client, uids, g_metadata)
        finally:
            if change_poller is not None:
                # schedule change_poller to die
                kill(change_poller)

    def resync_uids_impl(self):
        with session_scope(self.namespace_id) as db_session:
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

            chunk_size = 1000
            for entry in imap_uid_entries.yield_per(chunk_size):
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

    def __deduplicate_message_object_creation(self, db_session, raw_messages,
                                              account):
        """
        We deduplicate messages based on g_msgid: if we've previously saved a
        Message object for this raw message, we don't create a new one. But we
        do create a new ImapUid, associate it to the message, and update flags
        and categories accordingly.
        Note: we could do this prior to downloading the actual message
        body, but that's really more complicated than it's worth. This
        operation is not super common unless you're regularly moving lots
        of messages to trash or spam, and even then the overhead of just
        downloading the body is generally not that high.

        """
        new_g_msgids = {msg.g_msgid for msg in raw_messages}
        existing_g_msgids = g_msgids(self.namespace_id, db_session,
                                     in_=new_g_msgids)
        brand_new_messages = [m for m in raw_messages if m.g_msgid not in
                              existing_g_msgids]
        previously_synced_messages = [m for m in raw_messages if m.g_msgid in
                                      existing_g_msgids]
        if previously_synced_messages:
            log.info('saving new uids for existing messages',
                     count=len(previously_synced_messages))
            account = Account.get(self.account_id, db_session)
            folder = Folder.get(self.folder_id, db_session)
            for raw_message in previously_synced_messages:
                message_obj = db_session.query(Message).filter(
                    Message.namespace_id == self.namespace_id,
                    Message.g_msgid == raw_message.g_msgid).first()
                if message_obj is None:
                    log.warning(
                        'Message disappeared while saving new uid',
                        g_msgid=raw_message.g_msgid,
                        uid=raw_message.uid)
                    brand_new_messages.append(raw_message)
                    continue
                already_have_uid = (
                    (raw_message.uid, self.folder_id) in
                    {(u.msg_uid, u.folder_id) for u in message_obj.imapuids}
                )
                if already_have_uid:
                    log.warning('Skipping existing UID for message',
                                uid=raw_message.uid, message_id=message_obj.id)
                    continue
                uid = ImapUid(account=account,
                              folder=folder,
                              msg_uid=raw_message.uid,
                              message=message_obj)
                uid.update_flags(raw_message.flags)
                uid.update_labels(raw_message.g_labels)
                common.update_message_metadata(
                    db_session, account, message_obj, uid.is_draft)
                db_session.commit()

        return brand_new_messages

    def add_message_to_thread(self, db_session, message_obj, raw_message):
        """Associate message_obj to the right Thread object, creating a new
        thread if necessary. We rely on Gmail's threading as defined by
        X-GM-THRID instead of our threading algorithm."""
        # NOTE: g_thrid == g_msgid on the first message in the thread
        message_obj.g_msgid = raw_message.g_msgid
        message_obj.g_thrid = raw_message.g_thrid
        with db_session.no_autoflush:
            # Disable autoflush so we don't try to flush a message with null
            # thread_id.
            message_obj.thread = ImapThread.from_gmail_message(
                db_session, self.namespace_id, message_obj)

    def download_and_commit_uids(self, crispin_client, uids):
        start = datetime.utcnow()
        raw_messages = crispin_client.uids(uids)
        if not raw_messages:
            return
        new_uids = set()
        with self.syncmanager_lock:
            with session_scope(self.namespace_id) as db_session:
                account = Account.get(self.account_id, db_session)
                folder = Folder.get(self.folder_id, db_session)
                raw_messages = self.__deduplicate_message_object_creation(
                    db_session, raw_messages, account)
                if not raw_messages:
                    return 0

                for msg in raw_messages:
                    uid = self.create_message(db_session, account, folder,
                                              msg)
                    if uid is not None:
                        db_session.add(uid)
                        db_session.commit()
                        new_uids.add(uid)

        log.info('Committed new UIDs',
                 new_committed_message_count=len(new_uids))
        # If we downloaded uids, record message velocity (#uid / latency)
        if self.state == "initial" and len(new_uids):
            self._report_message_velocity(datetime.utcnow() - start,
                                          len(new_uids))

        if self.is_first_message:
            self._report_first_message()
            self.is_first_message = False

        self.saved_uids.update(new_uids)

    def expand_uids_to_download(self, crispin_client, uids, metadata):
        # During Gmail initial sync, we expand threads: given a UID to
        # download, we want to also download other UIDs on the same thread, so
        # that you don't see incomplete thread views for the duration of the
        # sync. Given a 'seed set' of UIDs, this function returns a generator
        # which yields the 'expanded' set of UIDs to download.
        thrids = OrderedDict()
        for uid in sorted(uids, reverse=True):
            g_thrid = metadata[uid].g_thrid
            if g_thrid in thrids:
                thrids[g_thrid].append(uid)
            else:
                thrids[g_thrid] = [uid]

        for g_thrid, uids in thrids.items():
            g_msgid = metadata[uids[0]].g_msgid
            # Because `uids` is ordered newest-to-oldest here, uids[0] is the
            # last UID on the thread. If g_thrid is equal to its g_msgid, that
            # means it's also the first UID on the thread. In that case, we can
            # skip thread expansion for greater sync throughput.
            if g_thrid != g_msgid:
                uids = set(uids).union(crispin_client.expand_thread(g_thrid))
                metadata.update(crispin_client.g_metadata(uids))
            for uid in sorted(uids, reverse=True):
                yield uid

    def batch_download_uids(self, crispin_client, uids, metadata,
                            max_download_bytes=MAX_DOWNLOAD_BYTES,
                            max_download_count=MAX_DOWNLOAD_COUNT):
        expanded_pending_uids = self.expand_uids_to_download(
            crispin_client, uids, metadata)
        count = 0
        while True:
            dl_size = 0
            batch = []
            while (dl_size < max_download_bytes and
                   len(batch) < max_download_count):
                try:
                    uid = expanded_pending_uids.next()
                except StopIteration:
                    break
                batch.append(uid)
                if uid in metadata:
                    dl_size += metadata[uid].size
            if not batch:
                return
            self.download_and_commit_uids(crispin_client, batch)
            self.heartbeat_status.publish()
            count += len(batch)
            if self.throttled and count >= THROTTLE_COUNT:
                # Throttled accounts' folders sync at a rate of
                # 1 message/ minute, after the first approx. THROTTLE_COUNT
                # messages for this batch are synced.
                # Note this is an approx. limit since we use the #(uids),
                # not the #(messages).
                sleep(THROTTLE_WAIT)

    @property
    def throttled(self):
        with session_scope(self.namespace_id) as db_session:
            account = db_session.query(Account).get(self.account_id)
            throttled = account.throttled

        return throttled


def g_msgids(namespace_id, session, in_):
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
            filter(Message.namespace_id == namespace_id).all()
        return sorted(g_msgid for g_msgid, in query if g_msgid in in_)
    # But in the normal case that in_ only has a few elements, it's way better
    # to not fetch a bunch of values from MySQL only to return a few of them.
    query = session.query(Message.g_msgid). \
        filter(Message.namespace_id == namespace_id,
               Message.g_msgid.in_(in_)).all()
    return {g_msgid for g_msgid, in query}
