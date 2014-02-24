# deal with unicode literals: http://www.python.org/dev/peps/pep-0263/
# vim: set fileencoding=utf-8 :
"""
----------------
IMAP SYNC ENGINE
----------------

Okay, here's the deal.

The IMAP sync engine runs per-folder on each account. This allows behaviour
like the Inbox to receive new mail via polling while we're still running the
initial sync on a huge All Mail folder.

Only one initial sync can be running per-account at a time, to avoid
hammering the IMAP backend too hard (Gmail shards per-user, so parallelizing
folder download won't actually increase our throughput anyway).

Any time we reconnect, we have to make sure the folder's uidvalidity hasn't
changed, and if it has, we need to update the UIDs for any messages we've
already downloaded. A folder's uidvalidity cannot change during a session
(SELECT during an IMAP session starts a session on a folder) (see
http://tools.ietf.org/html/rfc3501#section-2.3.1.1).

Note that despite a session giving you a HIGHESTMODSEQ at the start of a
SELECT, that session will still always give you the latest message list
including adds, deletes, and flag changes that have happened since that
highestmodseq. (In Gmail, there is a small delay between changes happening on
the web client and those changes registering on a connected IMAP session,
though bizarrely the HIGHESTMODSEQ is updated immediately.) So we have to keep
in mind that the data may be changing behind our backs as we're syncing.
Fetching info about UIDs that no longer exist is not an error but gives us
empty data.

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

--------------
SESSION SCOPES
--------------

Database sessions for each ImapFolderSyncMonitor are held for the duration of
the action (e.g. poll, initial sync). Sessions for ZeroRPC requests are held
for the duration of the request, if they need database access. ImapSyncMonitor
only briefly accesses the database to start up and grabs a transient session
for that.
"""
from __future__ import division

from datetime import datetime
from gc import collect as garbage_collect

from geventconnpool import retry
from gevent import Greenlet, sleep

from inbox.util.itert import chunk, partition

from ..log import get_logger
from ..crispin import new_crispin
from ..models import session_scope
from ..models import imapaccount as account
from ..models.tables import ImapAccount, Namespace, FolderSync
from ..models.namespace import db_write_lock

from .exc import UIDInvalid
from .base import gevent_check_join, verify_db, save_folder_names
from .base import BaseMailSyncMonitor

from sqlalchemy.orm.exc import NoResultFound

class ImapSyncMonitor(BaseMailSyncMonitor):
    """ Top-level controller for an account's mail sync. Spawns individual
        FolderSync greenlets for each folder.

        poll_frequency and heartbeat are in seconds.
    """
    def __init__(self, account_id, namespace_id, email_address, provider,
            status_cb, heartbeat=1, poll_frequency=30):

        self.shared_state = {
                # IMAP folders are kept up-to-date via polling
                'poll_frequency': poll_frequency,
                'syncmanager_lock': db_write_lock(namespace_id),
                }

        self.folder_monitors = []
        if not hasattr(self, 'folder_state_handlers'):
            self.folder_state_handlers = {
                    'initial': initial_sync,
                    'initial uidinvalid': resync_uids_from('initial'),
                    'poll': poll,
                    'poll uidinvalid': resync_uids_from('poll'),
                    'finish': lambda c, s, l, f, st: 'finish',
                    }

        BaseMailSyncMonitor.__init__(self, account_id, email_address, provider,
                status_cb, heartbeat)

    def sync(self):
        """ Start per-folder syncs. Only have one per-folder sync in the
            'initial' state at a time.
        """
        with session_scope() as db_session:
            saved_states = dict((saved_state.folder_name, saved_state.state) \
                    for saved_state in db_session.query(FolderSync).filter_by(
                    imapaccount_id=self.account_id))
            crispin_client = new_crispin(self.account_id, self.provider)
            with crispin_client.pool.get() as c:
                sync_folders = crispin_client.sync_folders(c)
                imapaccount = db_session.query(ImapAccount).get(self.account_id)
                folder_names = crispin_client.folder_names(c)
                save_folder_names(self.log, imapaccount, folder_names,
                        db_session)
        for folder in sync_folders:
            if saved_states.get(folder) != 'finish':
                self.log.info("Initializing folder sync for {0}".format(folder))
                thread = ImapFolderSyncMonitor(self.account_id, folder,
                        self.email_address, self.provider, self.shared_state,
                        self.folder_state_handlers)
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

class ImapFolderSyncMonitor(Greenlet):
    """ Per-folder sync engine. """

    def __init__(self, account_id, folder_name, email_address, provider,
            shared_state, state_handlers):
        self.folder_name = folder_name
        self.shared_state = shared_state
        self.state_handlers = state_handlers
        self.state = None

        self.log = get_logger(account_id, 'sync')
        self.crispin_client = new_crispin(account_id, provider)

        Greenlet.__init__(self)

    def _run(self):
        with session_scope() as db_session:
            try:
                foldersync = db_session.query(FolderSync).filter_by(
                        imapaccount_id=self.crispin_client.account_id,
                        folder_name=self.folder_name).one()
            except NoResultFound:
                foldersync = FolderSync(
                        imapaccount_id=self.crispin_client.account_id,
                        folder_name=self.folder_name)
                db_session.add(foldersync)
                db_session.commit()
            self.state = foldersync.state
            # NOTE: The parent ImapSyncMonitor handler could kill us at any
            # time if it receives a shutdown command. The shutdown command is
            # equivalent to ctrl-c.
            while True:
                try:
                    self.state = foldersync.state = \
                            self.state_handlers[foldersync.state](
                                    self.crispin_client, db_session, self.log,
                                    self.folder_name, self.shared_state)
                except UIDInvalid:
                    self.state = foldersync.state = self.state + ' uidinvalid'
                # State handlers are idempotent, so it's okay if we're killed
                # between the end of the handler and the commit.
                db_session.commit()
                if self.state == 'finish':
                    return

def resync_uids_from(previous_state):
    @retry
    def resync_uids(crispin_client, log, db_session, folder_name, shared_state):
        """ Call this when UIDVALIDITY is invalid to fix up the database.

        What happens here is we fetch new UIDs from the IMAP server and
        match them with X-GM-MSGIDs and sub in the new UIDs for the old. No
        messages are re-downloaded.
        """
        log.info("UIDVALIDITY for {0} has changed; resyncing UIDs".format(folder_name))
        raise NotImplementedError
        return previous_state
    return resync_uids

@retry
def initial_sync(crispin_client, db_session, log, folder_name, shared_state):
    return base_initial_sync(crispin_client, db_session, log, folder_name,
            shared_state, imap_initial_sync)

def base_initial_sync(crispin_client, db_session, log, folder_name,
        shared_state, initial_sync_fn):
    """ Downloads entire messages.

    This method may be retried as many times as you like; it will pick up where
    it left off, delete removed messages if things disappear between restarts,
    and only complete once we have all the UIDs in the given folder locally.
    """
    log.info('Starting initial sync for {0}'.format(folder_name))

    local_uids = account.all_uids(crispin_client.account_id,
            db_session, folder_name)

    with crispin_client.pool.get() as c:
        crispin_client.select_folder(folder_name,
                uidvalidity_cb(db_session, crispin_client.account_id), c)

        initial_sync_fn(crispin_client, db_session, log, folder_name,
                shared_state, local_uids, c)

    verify_db(crispin_client, db_session)

    return 'poll'

@retry
def poll(crispin_client, db_session, log, folder_name, shared_state):
    return base_poll(crispin_client, db_session, log, folder_name,
            shared_state, imap_highestmodseq_update)

def base_poll(crispin_client, db_session, log, folder_name, shared_state,
        highestmodseq_fn):
    """ It checks for changed message metadata and new messages using
        CONDSTORE / HIGHESTMODSEQ and also checks for deleted messages.

        We may wish to frob update frequencies based on which folder
        a user has visible in the UI as well, and whether or not a user
        is actually logged in on any devices.
    """
    log.info("polling {0}".format(folder_name))

    with crispin_client.pool.get() as c:
        saved_validity = account.get_uidvalidity(crispin_client.account_id,
                db_session, folder_name)
        # we use status instead of select here because it's way faster and
        # we're not sure we want to commit to an IMAP session yet
        status = crispin_client.folder_status(folder_name, c)
        if status['HIGHESTMODSEQ'] > saved_validity.highestmodseq:
            crispin_client.select_folder(folder_name,
                    uidvalidity_cb(db_session,
                        crispin_client.account_id), c)
            highestmodseq_update(crispin_client, db_session, log, folder_name,
                    saved_validity.highestmodseq,
                    shared_state['status_cb'], highestmodseq_fn,
                    shared_state['syncmanager_lock'], c)

        shared_state['status_cb'](
            crispin_client.account_id, 'poll',
            (folder_name, datetime.utcnow().isoformat()))
        sleep(shared_state['poll_frequency'])

    return 'poll'

def highestmodseq_update(crispin_client, db_session, log, folder_name,
        last_highestmodseq, status_cb, highestmodseq_fn, syncmanager_lock, c):
    account_id = crispin_client.account_id
    new_highestmodseq = crispin_client.selected_highestmodseq
    new_uidvalidity = crispin_client.selected_uidvalidity
    log.info("Starting highestmodseq update on {0} (current HIGHESTMODSEQ: {1})".format(folder_name, new_highestmodseq))
    local_uids = account.all_uids(account_id, db_session, folder_name)
    changed_uids = crispin_client.new_and_updated_uids(last_highestmodseq, c)
    remote_uids = crispin_client.all_uids(c)

    if changed_uids:
        new, updated = new_or_updated(changed_uids, local_uids)
        log.info("{0} new and {1} updated UIDs".format(len(new), len(updated)))
        local_uids += new
        local_uids = set(local_uids) - remove_deleted_uids(account_id,
                db_session, log, folder_name, local_uids, remote_uids,
                syncmanager_lock, c)

        update_metadata(crispin_client, db_session, log, folder_name,
                updated, syncmanager_lock, c)

        highestmodseq_fn(crispin_client, db_session, log, folder_name,
                changed_uids, local_uids, status_cb, syncmanager_lock, c)
    else:
        log.info("No new or updated messages")

    remove_deleted_uids(crispin_client.account_id, db_session, log,
            folder_name, local_uids, remote_uids, syncmanager_lock, c)
    account.update_uidvalidity(account_id, db_session, folder_name,
            new_uidvalidity, new_highestmodseq)
    db_session.commit()

def imap_highestmodseq_update(crispin_client, db_session, log, folder_name,
        uids, local_uids, status_cb, syncmanager_lock, c):
    chunked_uid_download(crispin_client, db_session, log, folder_name, uids, 0,
            len(uids), status_cb, download_and_commit_uids,
            account.create_message, syncmanager_lock, c)

def uidvalidity_cb(db_session, account_id):
    def fn(folder, select_info):
        assert folder is not None and select_info is not None, \
                "must start IMAP session before verifying UID validity"
        saved_validity = account.get_uidvalidity(account_id, db_session, folder)
        selected_uidvalidity = select_info['UIDVALIDITY']
        if saved_validity and not account.uidvalidity_valid(account_id,
                db_session, selected_uidvalidity, folder,
                saved_validity.uid_validity):
            raise UIDInvalid("folder: {0}, remote uidvalidity: {1}, cached uidvalidity: {2}".format(folder, selected_uidvalidity, saved_validity.uid_validity))
        return select_info
    return fn

def new_or_updated(uids, local_uids):
    """ HIGHESTMODSEQ queries return a list of messages that are *either*
        new *or* updated. We do different things with each, so we need to
        sort out which is which.
    """
    return partition(lambda x: x in local_uids, uids)

def imap_initial_sync(crispin_client, db_session, log, folder_name,
        shared_state, local_uids, c):
    check_flags(crispin_client, db_session, log, folder_name, local_uids,
            shared_state['syncmanager_lock'], c)

    remote_uids = crispin_client.all_uids(c)
    log.info("Found {0} UIDs for folder {1}".format(len(remote_uids),
        folder_name))
    log.info("Already have {0} UIDs".format(len(local_uids)))

    local_uids = set(local_uids) - remove_deleted_uids(
            crispin_client.account_id, db_session, log, folder_name,
            local_uids, remote_uids, shared_state['syncmanager_lock'], c)

    unknown_uids = set(remote_uids) - set(local_uids)

    chunked_uid_download(crispin_client, db_session, log, folder_name,
            unknown_uids, len(local_uids), len(remote_uids),
            shared_state['status_cb'], shared_state['syncmanager_lock'],
            download_and_commit_uids, account.create_message, c)

def check_flags(crispin_client, db_session, log, folder_name, local_uids,
        syncmanager_lock, c):
    """
    If we have a saved uidvalidity for this folder, make sure the folder hasn't
    changed since we saved it. Otherwise we need to query for flag changes too.
    """
    saved_validity = account.get_uidvalidity(crispin_client.account_id,
            db_session, folder_name)
    if saved_validity is not None:
        last_highestmodseq = saved_validity.highestmodseq
        if last_highestmodseq > crispin_client.selected_highestmodseq:
            uids = crispin_client.new_and_updated_uids(last_highestmodseq, c)
            if uids:
                _, updated = new_or_updated(uids, local_uids)
                update_metadata(crispin_client, db_session, log, folder_name,
                        updated, syncmanager_lock, c)

def chunked_uid_download(crispin_client, db_session, log,
        folder_name, uids, num_local_messages, num_total_messages, status_cb,
        syncmanager_lock, download_commit_fn, msg_create_fn, c):
    log.info("{0} uids left to fetch".format(len(uids)))

    if uids:
        chunk_size = crispin_client.CHUNK_SIZE
        log.info("Starting sync for {0} with chunks of size {1}"\
                .format(folder_name, chunk_size))
        # we prioritize message download by reverse-UID order, which
        # generally puts more recent messages first
        for uids in chunk(reversed(uids), chunk_size):
            num_local_messages += download_commit_fn(crispin_client,
                    db_session, log, folder_name, uids, msg_create_fn,
                    syncmanager_lock, c)

            percent_done = (num_local_messages / num_total_messages) * 100
            status_cb(crispin_client.account_id,
                    'initial', (folder_name, percent_done))
            log.info("Syncing %s -- %.2f%% (%i/%i)" % (folder_name,
                percent_done, num_local_messages, num_total_messages))
        log.info("Saved all messages and metadata on {0} to UIDVALIDITY {1} / HIGHESTMODSEQ {2}".format(folder_name, crispin_client.selected_uidvalidity, crispin_client.selected_highestmodseq))

def safe_download(crispin_client, log, uids, c):
    try:
        raw_messages = crispin_client.uids(uids, c)
    except MemoryError, e:
        log.error("Ran out of memory while fetching UIDs %s" % uids)
        raise e

    return raw_messages

def create_db_objects(account_id, db_session, log, folder_name, raw_messages,
        msg_create_fn):
    new_imapuids = []
    # TODO: Detect which namespace to add message to. (shared folders)
    # Look up message thread,
    acc = db_session.query(ImapAccount).join(Namespace).filter_by(
            id=account_id).one()
    for msg in raw_messages:
        uid = msg_create_fn(db_session, log, acc, folder_name, *msg)
        if uid is not None:
            new_imapuids.append(uid)

    # imapuid, message, thread, labels
    return new_imapuids

def download_and_commit_uids(crispin_client, db_session, log, folder_name,
        uids, msg_create_fn, syncmanager_lock, c):
    raw_messages = safe_download(crispin_client, log, uids, c)
    with syncmanager_lock:
        new_imapuids = create_db_objects(crispin_client.account_id, db_session,
                log, folder_name, raw_messages, msg_create_fn)
        commit_uids(db_session, log, new_imapuids)
    return len(new_imapuids)

def commit_uids(db_session, log, new_imapuids):
    new_messages = [item.message for item in new_imapuids]

    # Save message part blobs before committing changes to db.
    for msg in new_messages:
        threads = [Greenlet.spawn(part.save, part._data) \
                for part in msg.parts if hasattr(part, '_data')]
        # Fatally abort if part saves error out. Messages in this
        # chunk will be retried when the sync is restarted.
        gevent_check_join(log, threads,
                "Could not save message parts to blob store!")
        # clear data to save memory
        for part in msg.parts:
            part._data = None

    garbage_collect()

    db_session.add_all(new_imapuids)
    db_session.commit()

    # NOTE: indexing temporarily disabled because xapian is leaking fds :/
    # trigger_index_update(self.account.namespace.id)

def remove_deleted_uids(account_id, db_session, log, folder_name,
        local_uids, remote_uids, syncmanager_lock, c):
    """ Works as follows:
        1. Do a LIST on the current folder to see what messages are on the
            server.
        2. Compare to message uids stored locally.
        3. Purge messages we have locally but not on the server. Ignore
            messages we have on the server that aren't local.
    """
    if len(remote_uids) > 0 and len(local_uids) > 0:
        assert type(remote_uids[0]) != type('')

    to_delete = set(local_uids) - set(remote_uids)
    if to_delete:
        # We need to grab the lock for this because deleting ImapUids may
        # cascade to Messages and FolderItems and Threads. No one else messes
        # with ImapUids, but the exposed datastore elements are another story.
        with syncmanager_lock:
            account.remove_messages(account_id, db_session, to_delete, folder_name)
            db_session.commit()

        log.info("Deleted {0} removed messages from {1}".format(
            len(to_delete), folder_name))

    return to_delete

def update_metadata(crispin_client, db_session, log, folder_name, uids,
        syncmanager_lock, c):
    """ Update flags (the only metadata that can change). """
    # bigger chunk because the data being fetched here is very small
    for uids in chunk(uids, 5*crispin_client.CHUNK_SIZE):
        new_flags = crispin_client.flags(uids, c)
        assert sorted(uids, key=int) == sorted(new_flags.keys(), key=int), \
                "server uids != local uids"
        log.info("new flags: {0}".format(new_flags))
        with syncmanager_lock:
            account.update_metadata(crispin_client.account_id, db_session,
                    folder_name, uids, new_flags)
            db_session.commit()
