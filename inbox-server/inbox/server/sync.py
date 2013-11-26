# deal with unicode literals: http://www.python.org/dev/peps/pep-0263/
# vim: set fileencoding=utf-8 :
from __future__ import division

import os
import socket

from .config import config
from .sessionmanager import new_crispin

from .models import db_session, FolderItem, Message, Thread, UIDValidity
from .models import IMAPAccount, FolderSync
from sqlalchemy.orm.exc import NoResultFound

from ..util.itert import chunk, partition
from ..util.cache import set_cache, get_cache, rm_cache

from .log import configure_sync_logging, get_logger
log = get_logger()

from datetime import datetime

from gevent import Greenlet, sleep, joinall
from gevent.queue import Queue, Empty
from gevent.event import Event

import zerorpc

"""
---------------
THE SYNC ENGINE
---------------

Okay, here's the deal.

The sync engine runs per-folder on each account. This allows behaviour like
the Inbox to receive new mail via polling while we're still running the initial
sync on a huge All Mail folder.

Only one initial sync can be running per-account at a time, to avoid
hammering the IMAP backend too hard (Gmail shards per-user, so parallelizing
folder download won't actually increase our throughput anyway).

Any time we reconnect, we have to make sure the folder's uidvalidity hasn't
changed, and if it has, we need to update the UIDs for any messages we've
already downloaded. A folder's uidvalidity cannot change during a session
(SELECT during an IMAP session starts a session on a folder).

Folder sync state is stored in the FolderSync table to allow for restarts.

Here's the state machine:

        -----
        |   ----------------         ----------------------
        ∨   | initial sync | <-----> | initial uidinvalid |
----------  ----------------         ----------------------
| finish |          |
----------          ∨
        ^   ----------------         ----------------------
        |---|      poll    | <-----> |   poll uidinvalid  |
            ----------------         ----------------------
            |  ∧
            ----

We encapsulate sync engine instances in greenlets for cooperative coroutine
scheduling around network I/O.

We provide a ZeroRPC service for starting, stopping, and querying status on
running syncs. We don't provide knobs to start/stop sync instances at a
per-folder level, only at a per-account level. There's no good reason to be
able to do so, and leaving that configurability out simplifies the interface.

------------------------
A NOTE ABOUT CONCURRENCY
------------------------

In this current design, we don't manage to guarantee 100% deduplication on
messages from Gmail. We will always deduplicate message blocks thanks to
using S3 as a CAS filesystem, but "the same" message may end up with
multiple rows in the Message (and, subsequently, Block) tables if a race
between the different FolderSyncMonitor threads results in two or more
threads not noticing that we have a certain X-GM-MSGID already in the metadata
store and downloads the message again.

This happens rarely in practice, and is a small price to pay for the ability
to e.g. receive new INBOX messages at the same time as a large email archive
is downloading. Our database is still _correct_ and consistent with these
duplicated metadata rows, which is the important part.

We do, however, have to serialize message thread detection into a single
processing thread per account. Otherwise, a message in the same thread
arriving via multiple folders may cause duplicate thread rows, leaving the
database in an inconsistent state.
"""

### exceptions

class SyncException(Exception): pass

### main

def trigger_index_update(namespace_id):
    c = zerorpc.Client()
    c.connect(config.get('SEARCH_SERVER_LOC', None))
    c.index(namespace_id)

def safe_download(uids, folder, crispin_client):
    try:
        raw_messages = crispin_client.uids(uids)
        new_messages, new_folderitems = \
                crispin_client.account.messages_from_raw(folder, raw_messages)
    except MemoryError, e:
        log.error("Ran out of memory while fetching UIDs %s" % uids)
        raise e

    return new_messages, new_folderitems

class ThreadDetector(Greenlet):
    """ See "A NOTE ABOUT CONCURRENCY" in the block comment at the top of this
        file.
    """
    def __init__(self, log, heartbeat=1):
        self.inbox = Queue()
        self.log = log
        self.heartbeat = heartbeat

        self.clear_cache()

        Greenlet.__init__(self)

    def clear_cache(self):
        self.cache = dict()

    def _run(self):
        while True:
            try:
                messages, event = self.inbox.get_nowait()
                for msg in messages:
                    if msg._g_thrid in self.cache:
                        thread = self.cache[msg._g_thrid]
                        thread.update_from_message(msg)
                    else:
                        self.cache[msg._g_thrid] = \
                                Thread.from_message(msg, msg._g_thrid)
                self.clear_cache()
                event.set()
            except Empty:
                sleep(self.heartbeat)

class FolderSyncMonitor(Greenlet):
    """ Per-folder sync engine. """
    def __init__(self, folder_name, account, crispin_client, log, shared_state):
        self.folder_name = folder_name
        self.account = account
        self.crispin_client = crispin_client
        self.log = log
        self.shared_state = shared_state
        self.state = None

        self.state_handlers = {
                'initial': self.initial_sync,
                'initial uid invalid': lambda: self.resync_uids('initial'),
                'poll': self.poll,
                'poll uid invalid': lambda: self.resync_uids('poll'),
                'finish': lambda: 'finish',
                }

        Greenlet.__init__(self)

    def _run(self):
        try:
            foldersync = db_session.query(FolderSync).filter_by(
                    imapaccount=self.account,
                    folder_name=self.folder_name).one()
        except NoResultFound:
            foldersync = FolderSync(imapaccount=self.account,
                    folder_name=self.folder_name)
            db_session.add(foldersync)
            db_session.commit()
        self.state = foldersync.state
        # NOTE: The parent MailSyncMonitor handler could kill us at any time if
        # it receives a shutdown command. The shutdown command is equivalent to
        # ctrl-c.
        while True:
            self.state = foldersync.state = self.state_handlers[foldersync.state]()
            # The session should automatically mark this as dirty, but make
            # sure.
            db_session.add(foldersync)
            # State handlers are idempotent, so it's okay if we're killed
            # between the end of the handler and the commit.
            db_session.commit()
            if self.state == 'finish':
                return

    def resync_uids(self, previous_state):
        """ Call this when UIDVALIDITY is invalid to fix up the database.

        What happens here is we fetch new UIDs from the IMAP server and match
        them with X-GM-MSGIDs and sub in the new UIDs for the old. No messages
        are re-downloaded.
        """
        self.log.info("UIDVALIDITY for {0} has changed; resyncing UIDs".format(
            self.folder_name))
        raise Exception("Unimplemented")
        return previous_state

    def _new_or_updated(self, uids, local_uids):
        """ HIGHESTMODSEQ queries return a list of messages that are *either*
            new *or* updated. We do different things with each, so we need to
            sort out which is which.
        """
        return partition(lambda x: x in local_uids, uids)

    def initial_sync(self):
        """ Downloads entire messages and:
        1. sync folder => create TM, MM, BM
        2. expand threads => TM -> MM MM MM
        3. get related messages (can query IMAP for messages mapping thrids)

        For All Mail (Gmail-specific), we can skip the last step.
        For non-Gmail backends, we can skip #2, since we have no way to
        deduplicate threads server-side.
        """
        self.log.info('Starting initial sync for {0}'.format(self.folder_name))

        local_uids = self.account.all_uids(self.folder_name)
        self.crispin_client.select_folder(self.folder_name)

        remote_g_metadata = None
        cached_validity = self.account.get_uidvalidity(self.folder_name)
        if cached_validity is not None:
            if not self.account.uidvalidity_valid(
                    self.crispin_client.selected_uidvalidity,
                    self.crispin_client.selected_folder_name,
                    cached_validity.uid_validity):
                # bail bail bail
                return 'initial uidinvalid'
            # we can only do this if we have a cached validity; if there's
            # no cached validity it generally means we haven't previously run
            remote_g_metadata = self._retrieve_g_metadata_cache(local_uids,
                    cached_validity)

        if remote_g_metadata is None:
            remote_g_metadata = self.crispin_client.g_metadata(
                    uids=self.crispin_client.all_uids())
            set_cache(os.path.join(str(self.account.id), self.folder_name,
                "remote_g_metadata"), remote_g_metadata)
            # make sure uidvalidity is up-to-date
            if cached_validity is None:
                db_session.add(UIDValidity(
                    imapaccount=self.account, folder_name=self.folder_name,
                    uid_validity=self.crispin_client.selected_uidvalidity,
                    highestmodseq=self.crispin_client.selected_highestmodseq))
                db_session.commit()
            else:
                cached_validity.uid_validity = \
                        self.crispin_client.selected_uidvalidity
                cached_validity.highestmodseq = \
                        self.crispin_client.selected_highestmodseq
                db_session.add(cached_validity)
                db_session.commit()

        remote_uids = sorted(remote_g_metadata.keys(), key=int)
        self.log.info("Found {0} UIDs for folder {1}".format(
            len(remote_uids), self.folder_name))
        self.log.info("Already have {0} UIDs".format(len(local_uids)))

        deleted_uids = set(local_uids).difference(set(remote_uids))
        unknown_uids = set(remote_uids).difference(set(local_uids))

        if deleted_uids:
            self.account.remove_messages(deleted_uids, self.folder_name)
            self.log.info("Removed the following UIDs that no longer exist on the server: {0}".format(' '.join([str(u) for u in sorted(deleted_uids, key=int)])))
            local_uids = sorted(
                    list(set(local_uids).difference(deleted_uids)), key=int)

        full_download = self._deduplicate_message_download(
                remote_g_metadata, unknown_uids)

        self.log.info("{0} uids left to fetch".format(len(full_download)))

        self.log.info("Starting sync for {0} with chunks of size {1}".format(
            self.folder_name, self.crispin_client.CHUNK_SIZE))
        # we prioritize message download by reverse-UID order, which generally
        # puts more recent messages first
        num_local_messages = len(local_uids)
        for uids in chunk(reversed(full_download), self.crispin_client.CHUNK_SIZE):
            num_local_messages += self._download_new_messages(
                    uids, num_local_messages, len(remote_uids))

        # XXX TODO: check for consistency with datastore here before committing
        # state: download any missing messages, delete any messages that we
        # have that the server doesn't. that way, worst case if sync engine
        # bugs trickle through is we lose some flags.
        self.log.info("Saved all messages and metadata on {0} to UIDVALIDITY {1} / HIGHESTMODSEQ {2}".format(self.folder_name, self.crispin_client.selected_uidvalidity, self.crispin_client.selected_highestmodseq))

        # NOTE: thread expansion may change selected folder
        original_folder = self.folder_name
        if self.account.provider == 'Gmail' and \
                self.folder_name != self.crispin_client.folder_names['All']:
            self._download_expanded_threads(remote_g_metadata, remote_uids)

        # complete X-GM-MSGID mapping is no longer needed after initial sync
        rm_cache(os.path.join(str(self.account.id), self.folder_name,
            "remote_g_metadata"))

        self.log.info("Finished initial sync of {0}.".format(original_folder))
        if self.folder_name not in self.crispin_client.poll_folders:
            return 'finish'
        else:
            return 'poll'

    def _gevent_check_join(self, threads, errmsg):
        """ Block until all threads have completed and throw an error if threads
            are not successful.
        """
        joinall(threads)
        errors = [thread.exception for thread in threads if not thread.successful()]
        if errors:
            self.log.error(errmsg)
            for error in errors:
                self.log.error(error)
            raise SyncException("Fatal error encountered")

    def _download_new_messages(self, uids, num_local_messages, num_remote_messages):
        new_messages, new_folderitems = safe_download(uids,
                self.crispin_client.selected_folder_name, self.crispin_client)

        # Save message part blobs before committing changes to db.
        for msg in new_messages:
            threads = [Greenlet.spawn(part.save, part._data) \
                    for part in msg.parts if hasattr(part, '_data')]
            # Fatally abort if part saves error out. Messages in this
            # chunk will be retried when the sync is restarted.
            self._gevent_check_join(threads,
                    "Could not save message parts to blob store!")

        # XXX clear data on part objects to save memory?
        # garbge_collect()

        event = Event()
        self.shared_state['thread_callback']((new_messages, event))
        event.wait()

        db_session.add_all(new_folderitems)
        db_session.add_all(new_messages)
        db_session.commit()

        percent_done = (num_local_messages / num_remote_messages) * 100
        self.shared_state['status_callback'](self.account, 'initial',
                (self.folder_name, percent_done))
        self.log.info("Syncing %s -- %.2f%% (%i/%i)" % (
            self.folder_name, percent_done,
            num_local_messages, num_remote_messages))

        # trigger_index_update(self.account.namespace.id)
        return len(uids)

    def _add_new_folderitem(self, remote_g_metadata, uids):
        flags = self.crispin_client.flags(uids)

        # Since we prioritize download for messages in certain threads, we
        # may already have FolderItem entries despite calling this method.
        local_folder_uids = set([uid for uid, in \
                db_session.query(FolderItem.msg_uid).filter(
                    FolderItem.folder_name==self.crispin_client.selected_folder_name,
                    FolderItem.msg_uid.in_(uids))])
        uids = [uid for uid in uids if uid not in local_folder_uids]

        if uids:
            # collate message objects to relate the new folderitems
            folderitem_uid_for = dict([(metadata['msgid'], uid) for (uid, metadata) \
                    in remote_g_metadata.items() if uid in uids])
            folderitem_g_msgids = [remote_g_metadata[uid]['msgid'] for uid in uids]
            message_for = dict([(folderitem_uid_for[mm.g_msgid], mm) for \
                    mm in db_session.query(Message).filter( \
                        Message.g_msgid.in_(folderitem_g_msgids))])

            db_session.add_all(
                    [FolderItem(imapaccount_id=self.account.id,
                        folder_name=self.crispin_client.selected_folder_name,
                        msg_uid=uid, flags=flags[uid],
                        message=message_for[uid]) for uid in uids])
            db_session.commit()

    def _retrieve_g_metadata_cache(self, local_uids, cached_validity):
        self.log.info('Attempting to retrieve remote_g_metadata from cache')
        remote_g_metadata = get_cache(os.path.join(
            str(self.account.id), self.folder_name, "remote_g_metadata"))
        if remote_g_metadata is not None:
            self.log.info("Successfully retrieved remote_g_metadata cache")
            if self.crispin_client.selected_highestmodseq > \
                    cached_validity.highestmodseq:
                self._update_g_metadata_cache(remote_g_metadata, local_uids)
        else:
            self.log.info("No cached data found")
        return remote_g_metadata

    def _update_g_metadata_cache(self, remote_g_metadata, local_uids):
        """ If HIGHESTMODSEQ has changed since we saved the X-GM-MSGID cache,
            we need to query for any changes since then and update the saved
            data.
        """
        self.log.info("Updating cache with latest changes")
        # any uids we don't already have will be downloaded correctly
        # as usual, but updated uids need to be updated manually
        # XXX it may actually be faster to just query for X-GM-MSGID for the
        # whole folder rather than getting changed UIDs first; MODSEQ queries
        # are slow on large folders.
        modified = self.crispin_client.new_and_updated_uids(
                self.crispin_client.selected_highestmodseq)
        new, updated = self._new_or_updated(modified, local_uids)
        self.log.info("{0} new and {1} updated UIDs".format(len(new), len(updated)))
        # for new, query metadata and update cache
        remote_g_metadata.update(self.crispin_client.g_metadata(new))
        # filter out messages that have disappeared
        all_uids = set(self.crispin_client.all_uids())
        for uid in remote_g_metadata.keys():
            if uid not in all_uids:
                del remote_g_metadata[uid]
        set_cache("_".join([self.account.email_address, self.folder_name,
            "remote_g_metadata"]), remote_g_metadata)
        self.log.info("Updated cache with new messages")
        # for updated, it's easier to just update them now
        # bigger chunk because the data being fetched here is very small
        for uids in chunk(updated, 5*self.crispin_client.CHUNK_SIZE):
            self._update_metadata(uids)
        self.log.info("Updated metadata for modified messages")

    def _highestmodseq_update(self, folder, highestmodseq=None):
        if highestmodseq is None:
            highestmodseq = db_session.query(UIDValidity).filter_by(
                    account=self.account, folder_name=folder
                    ).one().highestmodseq
        uids = self.crispin_client.new_and_updated_uids(highestmodseq)
        log.info("Starting highestmodseq update on {0} (current HIGHESTMODSEQ: {1})".format(folder, self.crispin_client.selected_highestmodseq))
        if uids:
            local_uids = self.account.all_uids(self.folder_name)
            new, updated = self._new_or_updated(uids, local_uids)
            log.info("{0} new and {1} updated UIDs".format(len(new), len(updated)))

            remote_g_metadata = self.crispin_client.g_metadata(new)
            full_download = self._deduplicate_message_download(
                    remote_g_metadata, new)

            num_downloaded = 0
            for uids in chunk(full_download, self.crispin_client.CHUNK_SIZE):
                num_downloaded += self._download_new_messages(
                        uids, num_downloaded, len(full_download))

            # bigger chunk because the data being fetched here is very small
            for uids in chunk(updated, 5*self.crispin_client.CHUNK_SIZE):
                self._update_metadata(uids)
        else:
            log.info("No changes")

        self._remove_deleted_messages()
        self._update_cached_highestmodseq(folder)

    def _download_expanded_threads(self, remote_g_metadata, uids):
        """ So after you've downloaded e.g. Inbox messages, you can view
            the entire threads, even if they contain messages that aren't
            in the Inbox.

            NOTE: This method will change the selected folder to All Mail.
        """
        assert self.account.provider == 'Gmail', \
                "thread expansion only works with Gmail"
        assert self.folder_name != self.crispin_client.folder_names['All'], \
                "All Mail threads are already fully expanded"
        self.log.info("Expanding threads and downloading additional messages.")
        g_thrids = set([msg['thrid'] for uid, msg in remote_g_metadata.items() \
                if uid in uids])
        if g_thrids:
            self.log.info("{0} threads: {1}".format(self.folder_name, g_thrids))
            self.crispin_client.select_folder(self.crispin_client.folder_names['All'])
            thread_uids = self.crispin_client.expand_threads(g_thrids)
            self.log.info("All Mail UIDs: {0}".format(thread_uids))
            # need X-GM-MSGID in order to dedupe download
            g_metadata = self.crispin_client.g_metadata(thread_uids)
            to_download = self._deduplicate_message_download(g_metadata, thread_uids)
            self.log.info("{0} deduplicated messages to download".format(
                len(to_download)))
            num_downloaded = 0
            for uids in chunk(to_download, self.crispin_client.CHUNK_SIZE):
                num_downloaded += self._download_new_messages(
                        uids, num_downloaded, len(to_download))
            # NOTE: We intentionally don't re-select the original folder here,
            # since doing so may be slow and we don't usually need to do
            # anything after expanding threads.

    def _deduplicate_message_download(self, remote_g_metadata, uids):
        """ Deduplicate message download using X-GM-MSGID. """
        local_g_msgids = set(self.account.g_msgids(
                in_=[remote_g_metadata[uid]['msgid'] for uid in uids]))
        full_download, folderitem_only = partition(
                lambda uid: remote_g_metadata[uid]['msgid'] in local_g_msgids,
                sorted(uids, key=int))
        self.log.info("Skipping {0} uids downloaded via other folders".format(
            len(folderitem_only)))
        if len(folderitem_only) > 0:
            self._add_new_folderitem(remote_g_metadata, folderitem_only)

        return full_download

    def _update_cached_highestmodseq(self, folder, cached_validity=None):
        if cached_validity is None:
            cached_validity = db_session.query(UIDValidity).filter_by(
                    imapaccount_id=self.crispin_client.account.id,
                    folder_name=folder).one()
        cached_validity.highestmodseq = self.crispin_client.selected_highestmodseq
        db_session.add(cached_validity)
        db_session.commit()

    def poll(self):
        """ It checks for changed message metadata and new messages using
            CONDSTORE / HIGHESTMODSEQ and also checks for deleted messages.

            We may wish to frob update frequencies based on which folder
            a user has visible in the UI as well, and whether or not a user
            is actually logged in on any devices.
        """
        self.log.info("polling {0} {1}".format(
            self.account.email_address, self.folder_name))
        cached_validity = self.account.get_uidvalidity(self.folder_name)
        # we use status instead of select here because it's way faster and
        # we're not sure we want to commit to an IMAP session yet
        status = self.crispin_client.folder_status(self.folder_name)
        if status['HIGHESTMODSEQ'] > cached_validity.highestmodseq:
            self.crispin_client.select_folder(self.folder_name)
            if not self.account.uidvalidity_valid(
                    self.crispin_client.selected_uidvalidity,
                    self.crispin_client.selected_folder_name,
                    cached_validity.uid_validity):
                return 'poll uidinvalid'
            self._highestmodseq_update(self.folder_name,
                    cached_validity.highestmodseq)

        self.shared_state['status_callback'](
            self.account, 'poll', (self.folder_name, datetime.utcnow().isoformat()))
        sleep(self.shared_state['poll_frequency'])

        return 'poll'

    def _remove_deleted_messages(self):
        """ Works as follows:
            1. Do a LIST on the current folder to see what messages are on the
               server.
            2. Compare to message uids stored locally.
            3. Purge messages we have locally but not on the server. Ignore
               messages we have on the server that aren't local.
        """
        remote_uids = self.crispin_client.all_uids()
        local_uids = [uid for uid, in
                db_session.query(FolderItem.msg_uid).filter_by(
                    folder_name=self.crispin_client.selected_folder_name,
                    imapaccount_id=self.crispin_client.account.id)]
        if len(remote_uids) > 0 and len(local_uids) > 0:
            assert type(remote_uids[0]) != type('')

        to_delete = set(local_uids).difference(set(remote_uids))
        if to_delete:
            self.account.remove_messages(to_delete,
                    self.crispin_client.selected_folder_name)
            self.log.info("Deleted {0} removed messages".format(len(to_delete)))

    def _update_metadata(self, uids):
        """ Update flags (the only metadata that can change). """
        new_flags = self.crispin_client.flags(uids)
        assert sorted(uids, key=int) == sorted(new_flags.keys(), key=int), \
                "server uids != local uids"
        self.log.info("new flags: {0}".format(new_flags))
        self.account.update_metadata(self.crispin_client.selected_folder_name,
                uids, new_flags)
        db_session.commit()

class MailSyncMonitor(Greenlet):
    """ Top-level controller for an account's mail sync. Spawns individual
        FolderSync greenlets for each folder.

        poll_frequency and heartbeat are in seconds.
    """
    def __init__(self, account, status_callback, poll_frequency=30, heartbeat=1):
        self.inbox = Queue()
        # how often to check inbox
        self.heartbeat = heartbeat

        self.crispin_client = new_crispin(account.email_address)
        self.account = account
        self.log = configure_sync_logging(account)

        self.thread_detector = ThreadDetector(self.log)
        self.thread_detector.start()

        # stuff that might be updated later and we want to keep a shared
        # reference on child greenlets (per-folder sync engines)
        self.shared_state = {
                'poll_frequency': poll_frequency,
                'status_callback': status_callback,
                'thread_callback': \
                        lambda data: self.thread_detector.inbox.put_nowait(data),
                        }

        self.folder_monitors = []

        Greenlet.__init__(self)

    def _run(self):
        sync = Greenlet.spawn(self.sync)
        while not sync.ready():
            try:
                cmd = self.inbox.get_nowait()
                if not self.process_command(cmd):
                    self.log.info("Stopping sync for {0}".format(
                        self.account.email_address))
                    # ctrl-c, basically!
                    for monitor in self.folder_monitors:
                        monitor.kill(block=True)
                    sync.kill(block=True)
                    return
            except Empty:
                sleep(self.heartbeat)
        assert not sync.successful(), "mail sync should run forever!"
        raise sync.exception

    def process_command(self, cmd):
        """ Returns True if successful, or False if process should abort. """
        self.log.info("processing command {0}".format(cmd))
        return cmd != 'shutdown'

    def _thread_finished(self, thread):
        state = getattr(thread, 'state')
        return state == 'finish'

    def _thread_polling(self, thread):
        state = getattr(thread, 'state')
        return state is not None and state.startswith('poll')

    def sync(self):
        """ Start per-folder syncs. Only have one per-folder sync in the
            'initial' state at a time.
        """
        saved_states = dict((saved_state.folder_name, saved_state.state) \
                for saved_state in db_session.query(FolderSync).filter_by(
                imapaccount=self.account))
        for folder in self.crispin_client.sync_folders:
            if saved_states.get(folder) != 'finish':
                self.log.info("Initializing folder sync for {0}".format(folder))
                thread = FolderSyncMonitor(folder, self.account,
                        new_crispin(self.account.email_address),
                        self.log, self.shared_state)
                thread.start()
                self.folder_monitors.append(thread)
                while not self._thread_polling(thread) and \
                        not self._thread_finished(thread):
                    sleep(self.heartbeat)
                # Allow individual folder sync monitors to shut themselves down
                # after completing the initial sync.
                if self._thread_finished(thread):
                    self.log.info("Folder sync for {0} is done.".format(folder))
                    self.folder_monitors.pop()

        # Just hang out. We don't want to block, but we don't want to return
        # either, since that will let the threads go out of scope.
        while True:
            sleep(self.heartbeat)

### misc

def notify(account, mtype, message):
    """ Pass a message on to the notification dispatcher which deals with
        pubsub stuff for connected clients.
    """
    pass
    # self.log.info("message from {0}: [{1}] {2}".format(
    # account.email_address, mtype, message))

### zerorpc

class SyncService:
    """ ZeroRPC interface to syncing. """
    def __init__(self):
        # { account_id: MailSyncMonitor() }
        self.monitors = dict()
        # READ ONLY from API calls, writes happen from callbacks from monitor
        # greenlets.
        # { 'account_id': { 'state': 'initial sync', 'status': '0'} }
        # 'state' can be ['initial sync', 'poll']
        # 'status' is the percent-done for initial sync, polling start time otherwise
        # all data in here ought to be msgpack-serializable!
        self.statuses = dict()

        # Restart existing active syncs.
        # (Later we will want to partition these across different machines!)
        for email_address, in db_session.query(IMAPAccount.email_address).filter(
                IMAPAccount.sync_host!=None):
            self.start_sync(email_address)

    def start_sync(self, email_address=None):
        """ Starts all syncs if email_address not specified.
            If email_address doesn't exist, does nothing.
        """
        results = {}
        query = db_session.query(IMAPAccount)
        if email_address is not None:
            query = query.filter_by(email_address=email_address)
        fqdn = socket.getfqdn()
        for account in query:
            log.info("Starting sync for account {0}".format(account.email_address))
            if account.sync_host is not None and account.sync_host != fqdn:
                results[account.email_address] = \
                        'Account {0} is syncing on host {1}'.format(
                            account.email_address, account.sync_host)
            elif account.id not in self.monitors:
                try:
                    account.sync_lock()
                    def update_status(account, state, status):
                        """ I really really wish I were a lambda """
                        folder, progress = status
                        self.statuses.setdefault(
                                account.id, dict())[folder] = (state, progress)
                        notify(account, state, status)

                    monitor = MailSyncMonitor(account, update_status)
                    self.monitors[account.id] = monitor
                    monitor.start()
                    account.sync_host = fqdn
                    db_session.add(account)
                    db_session.commit()
                    results[account.email_address] = "OK sync started"
                except Exception as e:
                    raise
                    log.error(e.message)
                    results[account.email_address] = "ERROR error encountered"
            else:
                results[account.email_address] =  "OK sync already started"
        if email_address:
            if email_address in results:
                return results[email_address]
            else:
                return "OK no such user"
        return results

    def stop_sync(self, email_address=None):
        """ Stops all syncs if email_address not specified.
            If email_address doesn't exist, does nothing.
        """
        results = {}
        query = db_session.query(IMAPAccount)
        if email_address is not None:
            query = query.filter_by(email_address=email_address)
        fqdn = socket.getfqdn()
        for account in query:
            if not account.id in self.monitors:
                return "OK sync stopped already"
            if not account.sync_active:
                results[account.email_address] = "OK sync stopped already"
            try:
                assert account.sync_host == fqdn, "sync host FQDN doesn't match"
                # XXX Can processing this command fail in some way?
                self.monitors[account.id].inbox.put_nowait("shutdown")
                account.sync_host = None
                db_session.add(account)
                db_session.commit()
                account.sync_unlock()
                del self.monitors[account.id]
                results[account.email_address] = "OK sync stopped"
            except:
                results[account.email_address] = "ERROR error encountered"
        if email_address:
            if email_address in results:
                return results[email_address]
            else:
                return "OK no such user"
        return results

    def sync_status(self, account_id):
        return self.statuses.get(account_id)

    # XXX this should require some sort of auth or something, used from the
    # admin panel
    def status(self):
        return self.statuses
