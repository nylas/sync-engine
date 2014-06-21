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

from gevent import Greenlet, spawn, sleep
from gevent.queue import LifoQueue
from gevent.pool import Group
from sqlalchemy.orm.exc import NoResultFound

from inbox.util.concurrency import retry_wrapper
from inbox.util.itert import chunk
from inbox.log import get_logger
from inbox.crispin import connection_pool, retry_crispin
from inbox.models.session import session_scope
from inbox.models import Tag
from inbox.models.backends.imap import ImapAccount, FolderSync
from inbox.models.util import db_write_lock
from inbox.mailsync.exc import UIDInvalid
from inbox.mailsync.backends.imap import account
from inbox.mailsync.backends.base import (save_folder_names, create_db_objects,
                                          commit_uids, new_or_updated)
from inbox.mailsync.backends.base import BaseMailSyncMonitor


IDLE_FOLDERS = ['inbox', 'sent mail']


class ImapSyncMonitor(BaseMailSyncMonitor):
    """ Top-level controller for an account's mail sync. Spawns individual
        FolderSync greenlets for each folder.

        poll_frequency and heartbeat are in seconds.
    """
    def __init__(self, account_id, namespace_id, email_address, provider,
                 status_cb, heartbeat=1, poll_frequency=300):

        self.shared_state = {
            # IMAP folders are kept up-to-date via polling
            'poll_frequency': poll_frequency,
            'syncmanager_lock': db_write_lock(namespace_id),
        }

        self.folder_monitors = Group()
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
            saved_states = dict((saved_state.folder_name, saved_state.state)
                                for saved_state in
                                db_session.query(FolderSync).filter_by(
                                    account_id=self.account_id))
            with connection_pool(self.account_id).get() as crispin_client:
                sync_folders = crispin_client.sync_folders()
                imapaccount = db_session.query(ImapAccount)\
                    .get(self.account_id)
                save_folder_names(self.log, imapaccount,
                                  crispin_client.folder_names(), db_session)
                Tag.create_canonical_tags(imapaccount.namespace, db_session)
        for folder in sync_folders:
            if saved_states.get(folder) != 'finish':
                self.log.info("Initializing folder sync for {0}"
                              .format(folder))
                thread = ImapFolderSyncMonitor(self.account_id, folder,
                                               self.email_address,
                                               self.provider,
                                               self.shared_state,
                                               self.folder_state_handlers)
                thread.start()
                self.folder_monitors.add(thread)
                while not self._thread_polling(thread) and \
                        not self._thread_finished(thread):
                    sleep(self.heartbeat)
                # Allow individual folder sync monitors to shut themselves down
                # after completing the initial sync.
                if self._thread_finished(thread):
                    self.log.info("Folder sync for {} is done."
                                  .format(folder))
                    # NOTE: Greenlet is automatically removed from the group
                    # after finishing.

        self.folder_monitors.join()


class ImapFolderSyncMonitor(Greenlet):
    """ Per-folder sync engine. """

    def __init__(self, account_id, folder_name, email_address, provider,
                 shared_state, state_handlers):
        self.account_id = account_id
        self.folder_name = folder_name
        self.shared_state = shared_state
        self.state_handlers = state_handlers
        self.state = None
        self.conn_pool = connection_pool(self.account_id)

        self.log = get_logger(account_id, 'mailsync')

        Greenlet.__init__(self)

    def _run(self):
        return retry_wrapper(self._run_impl, self.log)

    def _run_impl(self):
        # We do NOT ignore soft deletes in the mail sync because it gets real
        # complicated handling e.g. when backends reuse imapids. ImapUid
        # objects are the only objects deleted by the mail sync backends
        # anyway.
        with session_scope(ignore_soft_deletes=False) as db_session:
            try:
                foldersync = db_session.query(FolderSync).filter_by(
                    account_id=self.account_id,
                    folder_name=self.folder_name).one()
            except NoResultFound:
                foldersync = FolderSync(account_id=self.account_id,
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
                            self.conn_pool, db_session, self.log,
                            self.folder_name, self.shared_state)
                except UIDInvalid:
                    self.state = foldersync.state = \
                        self.state + ' uidinvalid'
                # State handlers are idempotent, so it's okay if we're
                # killed between the end of the handler and the commit.
                db_session.commit()
                if self.state == 'finish':
                    return


def resync_uids_from(previous_state):
    @retry_crispin
    def resync_uids(conn_pool, db_session, log, folder_name,
                    shared_state):
        """ Call this when UIDVALIDITY is invalid to fix up the database.

        What happens here is we fetch new UIDs from the IMAP server and
        match them with X-GM-MSGIDs and sub in the new UIDs for the old. No
        messages are re-downloaded.
        """
        log.info("UIDVALIDITY for {0} has changed; resyncing UIDs"
                 .format(folder_name))
        raise NotImplementedError
        return previous_state
    return resync_uids


@retry_crispin
def initial_sync(conn_pool, db_session, log, folder_name, shared_state):
    with conn_pool.get() as crispin_client:
        return base_initial_sync(crispin_client, db_session, log, folder_name,
                                 shared_state, imap_initial_sync)


def base_initial_sync(crispin_client, db_session, log, folder_name,
                      shared_state, initial_sync_fn):
    """ Downloads entire messages.

    This function may be retried as many times as you like; it will pick up
    where it left off, delete removed messages if things disappear between
    restarts, and only complete once we have all the UIDs in the given folder
    locally.

    This function also starts up a secondary greenlet that checks for new
    messages periodically, to deal with the case of very large folders---it's
    a bad experience for the user to keep receiving old mail but not receive
    new mail! We use a LIFO queue to make sure we're downloading newest mail
    first.
    """
    log.info('Starting initial sync for {0}'.format(folder_name))

    local_uids = account.all_uids(crispin_client.account_id,
                                  db_session, folder_name)

    uid_download_stack = LifoQueue()

    crispin_client.select_folder(folder_name,
                                 uidvalidity_cb(db_session,
                                                crispin_client.account_id))

    initial_sync_fn(crispin_client, db_session, log, folder_name,
                    shared_state, local_uids, uid_download_stack)

    return 'poll'


@retry_crispin
def poll(conn_pool, db_session, log, folder_name, shared_state):
    with conn_pool.get() as crispin_client:
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
    saved_validity = account.get_uidvalidity(crispin_client.account_id,
                                             db_session, folder_name)

    # Start a session since we're going to IDLE below anyway...
    # This also resets the folder name cache, which we want in order to
    # detect folder/label additions and deletions.
    status = crispin_client.select_folder(
        folder_name,
        uidvalidity_cb(db_session,
                       crispin_client.account_id))

    log.debug("POLL current modseq: {} | saved modseq: {}".format(
        status['HIGHESTMODSEQ'], saved_validity.highestmodseq))

    if status['HIGHESTMODSEQ'] > saved_validity.highestmodseq:
        acc = db_session.query(ImapAccount).get(crispin_client.account_id)
        save_folder_names(log, acc, crispin_client.folder_names(), db_session)
        highestmodseq_update(crispin_client, db_session, log, folder_name,
                             saved_validity.highestmodseq,
                             shared_state['status_cb'], highestmodseq_fn,
                             shared_state['syncmanager_lock'])

    # We really only want to idle on a folder for new messages. Idling on
    # `All Mail` won't tell us when messages are archived from the Inbox
    # TODO make sure the server supports the IDLE command (Yahoo does not)

    if folder_name.lower() in IDLE_FOLDERS:
        status = crispin_client.select_folder(
            folder_name,
            uidvalidity_cb(db_session,
                           crispin_client.account_id))

        idle_frequency = 1800  # 30min

        log.info("Idling on {0} with {1} timeout".format(
            folder_name, idle_frequency))
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
        log.info("IDLE triggered poll or timeout reached on {0}"
                 .format(folder_name))
    else:
        log.info("Sleeping on {0} for {1} seconds".format(
            folder_name, shared_state['poll_frequency']))
        sleep(shared_state['poll_frequency'])

    return 'poll'


def highestmodseq_update(crispin_client, db_session, log, folder_name,
                         last_highestmodseq, status_cb, highestmodseq_fn,
                         syncmanager_lock):
    account_id = crispin_client.account_id
    new_highestmodseq = crispin_client.selected_highestmodseq
    new_uidvalidity = crispin_client.selected_uidvalidity
    log.info("Starting highestmodseq update on {} (current HIGHESTMODSEQ: {})"
             .format(folder_name, new_highestmodseq))
    local_uids = account.all_uids(account_id, db_session, folder_name)
    changed_uids = crispin_client.new_and_updated_uids(last_highestmodseq)
    remote_uids = crispin_client.all_uids()

    if changed_uids:
        new, updated = new_or_updated(changed_uids, local_uids)
        log.info("{0} new and {1} updated UIDs".format(len(new), len(updated)))
        local_uids += new
        with syncmanager_lock:
            log.debug("highestmodseq_update acquired syncmanager_lock")
            deleted_uids = remove_deleted_uids(account_id, db_session, log,
                                               folder_name, local_uids,
                                               remote_uids)

        local_uids = set(local_uids) - deleted_uids
        update_metadata(crispin_client, db_session, log, folder_name,
                        updated, syncmanager_lock)

        update_uid_counts(db_session, log, account_id, folder_name,
                          remote_uid_count=len(remote_uids),
                          download_uid_count=len(new),
                          update_uid_count=len(updated),
                          delete_uid_count=len(deleted_uids))

        highestmodseq_fn(crispin_client, db_session, log, folder_name,
                         changed_uids, local_uids, status_cb, syncmanager_lock)
    else:
        log.info("No new or updated messages")

    with syncmanager_lock:
        log.debug("highestmodseq_update acquired syncmanager_lock")
        remove_deleted_uids(crispin_client.account_id, db_session, log,
                            folder_name, local_uids, remote_uids)
    account.update_uidvalidity(account_id, db_session, folder_name,
                               new_uidvalidity, new_highestmodseq)
    db_session.commit()


def uid_list_to_stack(uids):
    """ UID download function needs a stack even for polling. """
    uid_download_stack = LifoQueue()
    for uid in sorted(uids, key=int):
        uid_download_stack.put(uid)
    return uid_download_stack


def imap_highestmodseq_update(crispin_client, db_session, log, folder_name,
                              uids, local_uids, status_cb, syncmanager_lock):
    uid_download_stack = uid_list_to_stack(uids)

    download_queued_uids(crispin_client, db_session, log, folder_name,
                         uid_download_stack, 0, uid_download_stack.qsize(),
                         status_cb, download_and_commit_uids,
                         account.create_imap_message, syncmanager_lock)


def uidvalidity_cb(db_session, account_id):
    def fn(folder, select_info):
        assert folder is not None and select_info is not None, \
            "must start IMAP session before verifying UID validity"
        saved_validity = account.get_uidvalidity(account_id, db_session,
                                                 folder)
        selected_uidvalidity = select_info['UIDVALIDITY']

        if saved_validity:
            is_valid = account.uidvalidity_valid(account_id, db_session,
                                                 selected_uidvalidity, folder,
                                                 saved_validity.uid_validity)
            if not is_valid:
                raise UIDInvalid(
                    'folder: {}, remote uidvalidity: {}, '
                    'cached uidvalidity: {}'.format(
                        folder, selected_uidvalidity,
                        saved_validity.uid_validity))
        return select_info
    return fn


def add_uids_to_stack(uids, uid_download_stack):
    for uid in sorted(uids, key=int):
        uid_download_stack.put(uid)


def imap_initial_sync(crispin_client, db_session, log, folder_name,
                      shared_state, local_uids, uid_download_stack):
    assert crispin_client.selected_folder_name == folder_name
    check_flags(crispin_client, db_session, log, folder_name, local_uids,
                shared_state['syncmanager_lock'])

    remote_uids = crispin_client.all_uids()
    log.info("Found {0} UIDs for folder {1}".format(len(remote_uids),
                                                    folder_name))
    log.info("Already have {0} UIDs".format(len(local_uids)))

    with shared_state['syncmanager_lock']:
        log.debug("imap_initial_sync acquired syncmanager_lock")
        deleted_uids = remove_deleted_uids(
            crispin_client.account_id, db_session, log, folder_name,
            local_uids, remote_uids)
    local_uids = set(local_uids) - deleted_uids

    add_uids_to_stack(set(remote_uids) - set(local_uids), uid_download_stack)

    new_uid_poller = spawn(check_new_uids, crispin_client.account_id,
                           crispin_client.PROVIDER, folder_name, log,
                           uid_download_stack, shared_state['poll_frequency'],
                           shared_state['syncmanager_lock'])

    download_queued_uids(crispin_client, db_session, log, folder_name,
                         uid_download_stack, len(local_uids), len(remote_uids),
                         shared_state['status_cb'],
                         shared_state['syncmanager_lock'],
                         download_and_commit_uids, account.create_imap_message)

    new_uid_poller.kill()


def check_new_uids(account_id, provider, folder_name, log, uid_download_stack,
                   poll_frequency, syncmanager_lock):
    """ Check for new UIDs and add them to the download stack.

    We do this by comparing local UID lists to remote UID lists, maintaining
    the invariant that (stack uids)+(local uids) == (remote uids).

    We also remove local messages that have disappeared from the remote, since
    it's totally probable that users will be archiving mail as the initial
    sync goes on.

    We grab a new IMAP connection from the pool for this to isolate its
    actions from whatever the main greenlet may be doing.

    Runs until killed. (Intended to be run in a greenlet.)
    """
    log.info("Spinning up new UID-check poller for {}".format(folder_name))
    with connection_pool(account_id).get() as crispin_client:
        with session_scope() as db_session:
            crispin_client.select_folder(folder_name,
                                         uidvalidity_cb(
                                             db_session,
                                             crispin_client.account_id))
        while True:
            remote_uids = set(crispin_client.all_uids())
            # We lock this section to make sure no messages are being
            # created while we make sure the queue is in a good state.
            with syncmanager_lock:
                log.debug("check_new_uids acquired syncmanager_lock")
                with session_scope(ignore_soft_deletes=False) as db_session:
                    local_uids = set(account.all_uids(account_id, db_session,
                                                      folder_name))
                    stack_uids = set(uid_download_stack.queue)
                    local_with_pending_uids = local_uids | stack_uids
                    deleted_uids = remove_deleted_uids(
                        account_id, db_session, log, folder_name, local_uids,
                        remote_uids)
                    log.info("Removed {} deleted UIDs from {}".format(
                        len(deleted_uids), folder_name))

                # filter out messages that have disappeared on the remote side
                new_uid_download_stack = {u for u in uid_download_stack.queue
                                          if u in remote_uids}

                # add in any new uids from the remote
                for uid in remote_uids:
                    if uid not in local_with_pending_uids:
                        new_uid_download_stack.add(uid)
                uid_download_stack.queue = sorted(new_uid_download_stack,
                                                  key=int)
            sleep(poll_frequency)


def check_flags(crispin_client, db_session, log, folder_name, local_uids,
                syncmanager_lock):
    """ Update message flags if folder has changed on the remote.

    If we have a saved uidvalidity for this folder, make sure the folder hasn't
    changed since we saved it. Otherwise we need to query for flag changes too.
    """
    saved_validity = account.get_uidvalidity(crispin_client.account_id,
                                             db_session, folder_name)
    if saved_validity is not None:
        last_highestmodseq = saved_validity.highestmodseq
        if last_highestmodseq > crispin_client.selected_highestmodseq:
            uids = crispin_client.new_and_updated_uids(last_highestmodseq)
            if uids:
                _, updated = new_or_updated(uids, local_uids)
                update_metadata(crispin_client, db_session, log, folder_name,
                                updated, syncmanager_lock)


def download_queued_uids(crispin_client, db_session, log,
                         folder_name, uid_download_stack, num_local_messages,
                         num_total_messages, status_cb, syncmanager_lock,
                         download_commit_fn, msg_create_fn):
    log.info("Starting sync for {}".format(folder_name))

    while not uid_download_stack.empty():
        uid = uid_download_stack.get_nowait()
        num_local_messages += download_commit_fn(
            crispin_client, db_session, log, folder_name, [uid],
            msg_create_fn, syncmanager_lock)

        report_progress(crispin_client, db_session, log,
                        crispin_client.selected_folder_name,
                        1, uid_download_stack.qsize())

    log.info(
        'Saved all messages and metadata on {} to UIDVALIDITY {} / '
        'HIGHESTMODSEQ {}'.format(folder_name,
                                  crispin_client.selected_uidvalidity,
                                  crispin_client.selected_highestmodseq))


def safe_download(crispin_client, log, uids):
    try:
        raw_messages = crispin_client.uids(uids)
    except MemoryError, e:
        log.error("Ran out of memory while fetching UIDs {}".format(uids))
        raise e

    return raw_messages


def download_and_commit_uids(crispin_client, db_session, log, folder_name,
                             uids, msg_create_fn, syncmanager_lock):
    raw_messages = safe_download(crispin_client, log, uids)
    with syncmanager_lock:
        log.debug("download_and_commit_uids acquired syncmanager_lock")
        new_imapuids = create_db_objects(crispin_client.account_id, db_session,
                                         log, folder_name, raw_messages,
                                         msg_create_fn)
        commit_uids(db_session, log, new_imapuids)
    return len(new_imapuids)


def remove_deleted_uids(account_id, db_session, log, folder_name, local_uids,
                        remote_uids):
    """ Remove imapuid entries that no longer exist on the remote.

    Works as follows:
        1. Do a LIST on the current folder to see what messages are on the
            server.
        2. Compare to message uids stored locally.
        3. Purge messages we have locally but not on the server. Ignore
            messages we have on the server that aren't local.

    Make SURE to be holding `syncmanager_lock` when calling this function;
    we do not grab it here to allow callers to lock higher level functionality.
    """
    if len(remote_uids) > 0 and len(local_uids) > 0:
        for elt in remote_uids:
            assert not isinstance(elt, str)

    to_delete = set(local_uids) - set(remote_uids)
    if to_delete:
        account.remove_messages(account_id, db_session, to_delete, folder_name)
        db_session.commit()

        log.info("Deleted {0} removed messages from {1}".format(
            len(to_delete), folder_name))

    return to_delete


def update_metadata(crispin_client, db_session, log, folder_name, uids,
                    syncmanager_lock):
    """ Update flags (the only metadata that can change). """
    # bigger chunk because the data being fetched here is very small
    for uids in chunk(uids, 5 * crispin_client.CHUNK_SIZE):
        new_flags = crispin_client.flags(uids)
        assert sorted(uids, key=int) == sorted(new_flags.keys(), key=int), \
            "server uids != local uids"
        log.info("new flags: {0}".format(new_flags))
        with syncmanager_lock:
            log.debug("update_metadata acquired syncmanager_lock")
            account.update_metadata(crispin_client.account_id, db_session,
                                    folder_name, uids, new_flags)
            db_session.commit()


def update_uid_counts(db_session, log, account_id, folder_name,
                      remote_uid_count=None, download_uid_count=None,
                      update_uid_count=None, delete_uid_count=None,
                      sync_type=None):
    foldersync = db_session.query(FolderSync).filter(
        FolderSync.account_id == account_id,
        FolderSync.folder_name == folder_name).one()

    metrics = dict(remote_uid_count=remote_uid_count,
                   download_uid_count=download_uid_count,
                   update_uid_count=update_uid_count,
                   delete_uid_count=delete_uid_count,
                   sync_type=sync_type,
                   # Record time we saved these counts
                   uid_checked_timestamp=datetime.utcnow(),
                   # Track num downloaded since `uid_checked_timestamp`
                   num_downloaded_since_timestamp=0)

    foldersync.update_sync_status(metrics)

    db_session.commit()


# TODO[k]: Periodically only?
def report_progress(crispin_client, db_session, log, folder_name,
                    downloaded_uid_count, num_remaining_messages):
    """
    Inform listeners of sync progress.

    It turns out that progress reporting with a download queue over IMAP is
    shockingly hard. :/ Sometimes the IMAP server caches the response to
    `crispin_client.num_uids()` and we can end up reporting a progress of
    > 100%. Not sure if there's a good way to kick the connection and make
    it recalculate. (We could do that via the IDLE thread if we had a ref
    to the crispin client.)

    Even if the UID doesn't appear in `crispin_client.all_uids()` though, we
    can still fetch it. So this behaviour doesn't affect actually downloading
    the new mail.

    """
    assert crispin_client.selected_folder_name == folder_name

    foldersync = db_session.query(FolderSync).filter(
        FolderSync.account_id == crispin_client.account_id,
        FolderSync.folder_name == folder_name).one()

    previous_count = foldersync.sync_status.get(
        'num_downloaded_since_timestamp', 0)
    metrics = dict(num_downloaded_since_timestamp=(previous_count +
                   downloaded_uid_count),
                   current_download_queue_size=num_remaining_messages,
                   queue_checked_at=datetime.utcnow())

    foldersync.update_sync_status(metrics)

    db_session.commit()

    log.info('Syncing {} -- {} msgs in queue'.format(
        folder_name, num_remaining_messages))
