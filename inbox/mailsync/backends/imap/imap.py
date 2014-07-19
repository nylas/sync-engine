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

Folder sync state is stored in the ImapFolderSyncStatus table to allow for
restarts.

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
from sqlalchemy.exc import DataError, IntegrityError

from inbox.util.concurrency import retry_and_report_killed
from inbox.util.itert import chunk
from inbox.log import get_logger
logger = get_logger()
from inbox.crispin import connection_pool, retry_crispin
from inbox.models.session import session_scope
from inbox.models import Tag, Folder
from inbox.models.backends.imap import ImapAccount, ImapFolderSyncStatus
from inbox.models.util import db_write_lock
from inbox.mailsync.exc import UidInvalid
from inbox.mailsync.reporting import report_stopped
from inbox.mailsync.backends.imap import account
from inbox.mailsync.backends.base import (save_folder_names,
                                          create_db_objects,
                                          commit_uids, new_or_updated,
                                          MailsyncError)
from inbox.mailsync.backends.base import BaseMailSyncMonitor


IDLE_FOLDERS = ['inbox', 'sent mail']


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
    def __init__(self, account_id, namespace_id, email_address, provider,
                 heartbeat=1, poll_frequency=300,
                 retry_fail_classes=[MailsyncError,
                                     ValueError, AttributeError,
                                     DataError, IntegrityError],
                 refresh_flags_max=2000):

        self.shared_state = {
            # IMAP folders are kept up-to-date via polling
            'poll_frequency': poll_frequency,
            'syncmanager_lock': db_write_lock(namespace_id),
            'refresh_flags_max': refresh_flags_max,
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
                                     heartbeat, retry_fail_classes)

    def sync(self):
        """ Start per-folder syncs. Only have one per-folder sync in the
            'initial' state at a time.
        """
        with session_scope(ignore_soft_deletes=False) as db_session:
            with connection_pool(self.account_id).get() as crispin_client:
                sync_folders = crispin_client.sync_folders()
                account = db_session.query(ImapAccount)\
                    .get(self.account_id)
                save_folder_names(self.log, account,
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
                self.log.error("Missing Folder object when starting sync",
                               folder_name=folder_name,
                               folder_id_for=folder_id_for)
                raise MailsyncError("Missing Folder '{}' on account {}"
                                    .format(folder_name, self.account_id))

            if saved_states.get(folder_name) != 'finish':
                self.log.info('initializing folder sync')
                thread = ImapFolderSyncMonitor(self.account_id, folder_name,
                                               folder_id_for[folder_name],
                                               self.email_address,
                                               self.provider,
                                               self.shared_state,
                                               self.folder_state_handlers,
                                               self.retry_fail_classes)
                thread.start()
                self.folder_monitors.add(thread)
                while not self._thread_polling(thread) and \
                        not self._thread_finished(thread):
                    sleep(self.heartbeat)
                # Allow individual folder sync monitors to shut themselves down
                # after completing the initial sync.
                if self._thread_finished(thread):
                    self.log.info('folder sync finished')
                    # NOTE: Greenlet is automatically removed from the group
                    # after finishing.

        self.folder_monitors.join()


class ImapFolderSyncMonitor(Greenlet):
    """ Per-folder sync engine. """

    def __init__(self, account_id, folder_name, folder_id,
                 email_address, provider, shared_state, state_handlers,
                 retry_fail_classes):
        self.account_id = account_id
        self.folder_name = folder_name
        self.folder_id = folder_id
        self.shared_state = shared_state
        self.state_handlers = state_handlers
        self.state = None
        self.conn_pool = connection_pool(self.account_id)
        self.retry_fail_classes = retry_fail_classes

        self.log = logger.new(account_id=account_id, folder=folder_name)

        Greenlet.__init__(self)
        self.link_value(lambda _: report_stopped(account_id=self.account_id,
                                                 folder_name=self.folder_name))

    def _run(self):
        return retry_and_report_killed(self._run_impl,
                                       account_id=self.account_id,
                                       folder_name=self.folder_name,
                                       logger=self.log,
                                       fail_classes=self.retry_fail_classes)

    def _run_impl(self):
        # We do NOT ignore soft deletes in the mail sync because it gets real
        # complicated handling e.g. when backends reuse imapids. ImapUid
        # objects are the only objects deleted by the mail sync backends
        # anyway.
        with session_scope(ignore_soft_deletes=False) as db_session:
            try:
                saved_folder_status = db_session.query(ImapFolderSyncStatus)\
                    .filter_by(account_id=self.account_id,
                               folder_id=self.folder_id).one()
            except NoResultFound:
                saved_folder_status = ImapFolderSyncStatus(
                    account_id=self.account_id, folder_id=self.folder_id)
                db_session.add(saved_folder_status)

            saved_folder_status.update_metrics(
                dict(run_state='running',
                     sync_start_time=datetime.utcnow(),
                     sync_end_time=None,
                     sync_error=None))

            db_session.commit()

            self.state = saved_folder_status.state
            # NOTE: The parent ImapSyncMonitor handler could kill us at any
            # time if it receives a shutdown command. The shutdown command is
            # equivalent to ctrl-c.
            while True:
                try:
                    self.state = saved_folder_status.state = \
                        self.state_handlers[saved_folder_status.state](
                            self.conn_pool, db_session, self.log,
                            self.folder_name, self.shared_state)
                except UidInvalid:
                    self.state = saved_folder_status.state = \
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
        log.error("UIDVALIDITY changed")
        raise NotImplementedError
        return previous_state
    return resync_uids


@retry_crispin
def initial_sync(conn_pool, db_session, log, folder_name, shared_state):
    with conn_pool.get() as crispin_client:
        return base_initial_sync(crispin_client, db_session, log, folder_name,
                                 shared_state, imap_initial_sync,
                                 account.create_imap_message)


def base_initial_sync(crispin_client, db_session, log, folder_name,
                      shared_state, initial_sync_fn, msg_create_fn):
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
    log.info('starting initial sync')

    local_uids = account.all_uids(crispin_client.account_id,
                                  db_session, folder_name)

    uid_download_stack = LifoQueue()

    crispin_client.select_folder(folder_name,
                                 uidvalidity_cb(db_session,
                                                crispin_client.account_id))

    initial_sync_fn(crispin_client, db_session, log, folder_name,
                    shared_state, local_uids, uid_download_stack,
                    msg_create_fn)

    return 'poll'


@retry_crispin
def poll(conn_pool, db_session, log, folder_name, shared_state):
    """ Checks for changed, new, and deleted messages.

    We may wish to frob update frequencies based on which folder a user has
    visible in the UI as well, and whether or not a user is actually logged in
    on any devices.

    """
    with conn_pool.get() as crispin_client:
        return base_poll(crispin_client, db_session, log, folder_name,
                         shared_state, imap_poll_update,
                         account.create_imap_message)


def base_poll(crispin_client, db_session, log, folder_name, shared_state,
              download_fn, msg_create_fn, update_fn):
    """ Base polling logic for non-CONDSTORE IMAP servers.

    Local/remote UID comparison is used to detect new and deleted messages.

    Currently does not support synchronizing flag changes.
    """
    account_id = crispin_client.account_id

    status = crispin_client.select_folder(
        folder_name,
        uidvalidity_cb(db_session, account_id))
    log.debug("POLL current UIDNEXT: {}".format(status['UIDNEXT']))

    remote_uids = set(crispin_client.all_uids())
    local_uids = set(account.all_uids(
        account_id, db_session, folder_name))
    deleted_uids = remove_deleted_uids(
        account_id, db_session, log, folder_name, local_uids,
        remote_uids)
    local_uids -= deleted_uids
    log.info("Removed {} deleted UIDs from {}".format(
        len(deleted_uids), folder_name))
    to_download = remote_uids - local_uids
    log.info("UIDs to download: {}".format(to_download))
    if to_download:
        download_fn(crispin_client, db_session, log, folder_name,
                    to_download, local_uids, shared_state['syncmanager_lock'],
                    msg_create_fn)

    flags_max_nr = abs(shared_state['refresh_flags_max'])
    to_refresh = sorted(remote_uids - to_download)[-flags_max_nr:]
    log.info('UIDs to refresh: ', uids=to_refresh)
    if to_refresh:
        update_fn(crispin_client, db_session, log, folder_name,
                  to_refresh, shared_state['syncmanager_lock'])

    sleep(shared_state['poll_frequency'])
    return 'poll'


def condstore_base_poll(crispin_client, db_session, log, folder_name,
                        shared_state, highestmodseq_fn):
    """ Base polling logic for IMAP servers which support CONDSTORE and IDLE.

    The CONDSTORE / HIGHESTMODSEQ mechanism is used to detect new and changed
    messages that need syncing.

    """
    log.bind(state='poll')
    saved_folder_info = account.get_folder_info(crispin_client.account_id,
                                                db_session, folder_name)

    # Start a session since we're going to IDLE below anyway...
    # This also resets the folder name cache, which we want in order to
    # detect folder/label additions and deletions.
    status = crispin_client.select_folder(
        folder_name, uidvalidity_cb(db_session, crispin_client.account_id))

    log.debug(current_modseq=status['HIGHESTMODSEQ'],
              saved_modseq=saved_folder_info.highestmodseq)

    if status['HIGHESTMODSEQ'] > saved_folder_info.highestmodseq:
        acc = db_session.query(ImapAccount).get(crispin_client.account_id)
        save_folder_names(log, acc, crispin_client.folder_names(), db_session)
        highestmodseq_update(crispin_client, db_session, log, folder_name,
                             saved_folder_info.highestmodseq, highestmodseq_fn,
                             shared_state['syncmanager_lock'])

    # We really only want to idle on a folder for new messages. Idling on
    # `All Mail` won't tell us when messages are archived from the Inbox
    if folder_name.lower() in IDLE_FOLDERS:
        status = crispin_client.select_folder(
            folder_name, uidvalidity_cb(db_session, crispin_client.account_id))

        idle_frequency = 1800  # 30min

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
        log.info('IDLE sleeping', seconds=shared_state['poll_frequency'])
        sleep(shared_state['poll_frequency'])

    return 'poll'


def highestmodseq_update(crispin_client, db_session, log, folder_name,
                         last_highestmodseq, highestmodseq_fn,
                         syncmanager_lock):
    account_id = crispin_client.account_id
    new_highestmodseq = crispin_client.selected_highestmodseq
    new_uidvalidity = crispin_client.selected_uidvalidity
    log.info('starting highestmodseq update',
             current_highestmodseq=new_highestmodseq)
    local_uids = account.all_uids(account_id, db_session, folder_name)
    changed_uids = crispin_client.new_and_updated_uids(last_highestmodseq)
    remote_uids = crispin_client.all_uids()

    if changed_uids:
        new, updated = new_or_updated(changed_uids, local_uids)
        log.info(new_uid_count=len(new), updated_uid_count=len(updated))
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
                         changed_uids, local_uids, syncmanager_lock)
    else:
        log.info("No new or updated messages")

    with syncmanager_lock:
        log.debug("highestmodseq_update acquired syncmanager_lock")
        remove_deleted_uids(crispin_client.account_id, db_session, log,
                            folder_name, local_uids, remote_uids)
    account.update_folder_info(account_id, db_session, folder_name,
                               new_uidvalidity, new_highestmodseq)
    db_session.commit()


def uid_list_to_stack(uids):
    """ UID download function needs a stack even for polling. """
    uid_download_stack = LifoQueue()
    for uid in sorted(uids, key=int):
        uid_download_stack.put(uid)
    return uid_download_stack


def imap_poll_update(crispin_client, db_session, log, folder_name,
                     uids, local_uids, syncmanager_lock, msg_create_fn):
    uid_download_stack = uid_list_to_stack(uids)

    download_queued_uids(crispin_client, db_session, log, folder_name,
                         uid_download_stack, 0, uid_download_stack.qsize(),
                         syncmanager_lock, download_and_commit_uids,
                         msg_create_fn)


def uidvalidity_cb(db_session, account_id):
    def fn(folder_name, select_info):
        assert folder_name is not None and select_info is not None, \
            "must start IMAP session before verifying UIDVALIDITY"
        saved_folder_info = account.get_folder_info(account_id, db_session,
                                                    folder_name)
        selected_uidvalidity = select_info['UIDVALIDITY']

        if saved_folder_info:
            is_valid = account.uidvalidity_valid(account_id, db_session,
                                                 selected_uidvalidity,
                                                 folder_name,
                                                 saved_folder_info.uidvalidity)
            if not is_valid:
                raise UidInvalid(
                    'folder: {}, remote uidvalidity: {}, '
                    'cached uidvalidity: {}'.format(
                        folder_name, selected_uidvalidity,
                        saved_folder_info.uidvalidity))
        return select_info
    return fn


def add_uids_to_stack(uids, uid_download_stack):
    for uid in sorted(uids, key=int):
        uid_download_stack.put(uid)


def condstore_imap_initial_sync(crispin_client, db_session, log, folder_name,
                                shared_state, local_uids, uid_download_stack,
                                msg_create_fn):
    check_flags(crispin_client, db_session, log, folder_name, local_uids,
                shared_state['syncmanager_lock'])
    return imap_initial_sync(crispin_client, db_session, log, folder_name,
                             shared_state, local_uids, uid_download_stack,
                             msg_create_fn)


def imap_initial_sync(crispin_client, db_session, log, folder_name,
                      shared_state, local_uids, uid_download_stack,
                      msg_create_fn):
    assert crispin_client.selected_folder_name == folder_name

    remote_uids = crispin_client.all_uids()
    log.info(remote_uid_count=len(remote_uids))
    log.info(local_uid_count=len(local_uids))

    with shared_state['syncmanager_lock']:
        log.debug("imap_initial_sync acquired syncmanager_lock")
        deleted_uids = remove_deleted_uids(
            crispin_client.account_id, db_session, log, folder_name,
            local_uids, remote_uids)

    local_uids = set(local_uids) - deleted_uids

    new_uids = set(remote_uids) - local_uids
    add_uids_to_stack(new_uids, uid_download_stack)

    update_uid_counts(db_session, log, crispin_client.account_id, folder_name,
                      remote_uid_count=len(remote_uids),
                      download_uid_count=len(new_uids),
                      # flags are updated in imap_check_flags
                      update_uid_count=0,
                      delete_uid_count=len(deleted_uids),
                      sync_type='new' if len(local_uids) == 0 else 'resumed')

    new_uid_poller = spawn(check_new_uids, crispin_client.account_id,
                           folder_name, log,
                           uid_download_stack, shared_state['poll_frequency'],
                           shared_state['syncmanager_lock'])

    flags_refresh_poller = spawn(imap_check_flags, crispin_client.account_id,
                                 folder_name, log,
                                 shared_state['poll_frequency'],
                                 shared_state['syncmanager_lock'],
                                 shared_state['refresh_flags_max'])

    download_queued_uids(crispin_client, db_session, log, folder_name,
                         uid_download_stack, len(local_uids), len(remote_uids),
                         shared_state['syncmanager_lock'],
                         download_and_commit_uids, msg_create_fn)

    new_uid_poller.kill()
    flags_refresh_poller.kill()


def check_new_uids(account_id, folder_name, log, uid_download_stack,
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
    log.info("starting new UID-check poller")
    with connection_pool(account_id).get() as crispin_client:
        with session_scope(ignore_soft_deletes=False) as db_session:
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
                    log.info('remoted deleted uids', count=len(deleted_uids))

                # filter out messages that have disappeared on the remote side
                new_uid_download_stack = {u for u in uid_download_stack.queue
                                          if u in remote_uids}

                # add in any new uids from the remote
                for uid in remote_uids:
                    if uid not in local_with_pending_uids:
                        log.debug("adding new message {} to download queue"
                                  .format(uid))
                        new_uid_download_stack.add(uid)
                uid_download_stack.queue = sorted(new_uid_download_stack,
                                                  key=int)
            sleep(poll_frequency)


def check_flags(crispin_client, db_session, log, folder_name, local_uids,
                syncmanager_lock):
    """ Update message flags if folder has changed on the remote.

    If we have saved validity info for this folder, make sure the folder hasn't
    changed since we saved it. Otherwise we need to query for flag changes too.
    """
    saved_folder_info = account.get_folder_info(crispin_client.account_id,
                                                db_session, folder_name)
    if saved_folder_info is not None:
        last_highestmodseq = saved_folder_info.highestmodseq
        if last_highestmodseq > crispin_client.selected_highestmodseq:
            uids = crispin_client.new_and_updated_uids(last_highestmodseq)
            if uids:
                _, updated = new_or_updated(uids, local_uids)
                update_metadata(crispin_client, db_session, log, folder_name,
                                updated, syncmanager_lock)


def imap_check_flags(account_id, folder_name, log, poll_frequency,
                     syncmanager_lock, refresh_flags_max):
    """
    Periodically update message flags for those servers
    who don't support CONDSTORE.
    Runs until killed. (Intended to be run in a greenlet)

    Parameters
    ----------
    account_id : String
    folder_name : String
    log : Logger
    poll_frequency : Integer
        Number of seconds to wait between polls.
    syncmanager_lock : Locking Context Manager
    refresh_flags_max : Integer
        Maximum number of messages to check FLAGS of.

    """
    log.info("Spinning up new flags-refresher for ", folder_name=folder_name)
    with connection_pool(account_id).get() as crispin_client:
        with session_scope(ignore_soft_deletes=False) as db_session:
            crispin_client.select_folder(folder_name,
                                         uidvalidity_cb(
                                             db_session,
                                             crispin_client.account_id))
        while True:
            remote_uids = set(crispin_client.all_uids())
            local_uids = set(account.all_uids(account_id, db_session,
                                              folder_name))
            to_refresh = sorted(remote_uids & local_uids)[-refresh_flags_max:]

            update_metadata(crispin_client,
                            db_session,
                            log,
                            folder_name,
                            to_refresh,
                            syncmanager_lock)

            update_uid_counts(db_session,
                              log,
                              crispin_client.account_id,
                              folder_name,
                              update_uid_count=len(to_refresh))

            sleep(poll_frequency)


def download_queued_uids(crispin_client, db_session, log,
                         folder_name, uid_download_stack, num_local_messages,
                         num_total_messages, syncmanager_lock,
                         download_commit_fn, msg_create_fn):
    while not uid_download_stack.empty():
        # Defer removing UID from queue until after it's committed to the DB'
        # to avoid races with check_new_uids()
        # XXX this should be uid_download_stack.peek_nowait(), which is
        # currently buggy in gevent (patch pending)
        uid = uid_download_stack.queue[-1]
        log.debug("downloading UID {} in folder {}".format(uid, folder_name))
        num_local_messages += download_commit_fn(
            crispin_client, db_session, log, folder_name, [uid],
            msg_create_fn, syncmanager_lock)
        uid_download_stack.get_nowait()

        report_progress(crispin_client, db_session, log,
                        crispin_client.selected_folder_name,
                        1, uid_download_stack.qsize())

    log.info('saved all messages and metadata',
             new_uidvalidity=crispin_client.selected_uidvalidity,
             new_uidnext=crispin_client.selected_folder_info['UIDNEXT'])


def safe_download(crispin_client, log, uids):
    try:
        raw_messages = crispin_client.uids(uids)
    except MemoryError, e:
        log.error('ran out of memory while fetching UIDs', uids=uids)
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

        log.info('deleted removed messages', count=len(to_delete))

    return to_delete


def update_metadata(crispin_client, db_session, log, folder_name, uids,
                    syncmanager_lock):
    """ Update flags (the only metadata that can change). """
    # bigger chunk because the data being fetched here is very small
    for uids in chunk(uids, 5 * crispin_client.CHUNK_SIZE):
        new_flags = crispin_client.flags(uids)
        # messages can disappear in the meantime; we'll update them next sync
        uids = [uid for uid in uids if uid in new_flags]
        log.info("new flags ", new_flags=new_flags, folder_name=folder_name)
        with syncmanager_lock:
            log.debug("update_metadata acquired syncmanager_lock")
            account.update_metadata(crispin_client.account_id, db_session,
                                    folder_name, uids, new_flags)
            db_session.commit()


def update_uid_counts(db_session, log, account_id, folder_name, **kwargs):
    saved_status = db_session.query(ImapFolderSyncStatus).join(Folder).filter(
        ImapFolderSyncStatus.account_id == account_id,
        Folder.name == folder_name).one()

    # Record time we saved these counts +
    # Track num downloaded since `uid_checked_timestamp`
    metrics = dict(uid_checked_timestamp=datetime.utcnow(),
                   num_downloaded_since_timestamp=0)
    metrics.update(kwargs)

    saved_status.update_metrics(metrics)

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

    saved_status = db_session.query(ImapFolderSyncStatus).join(Folder).filter(
        ImapFolderSyncStatus.account_id == crispin_client.account_id,
        Folder.name == folder_name).one()

    previous_count = saved_status.metrics.get(
        'num_downloaded_since_timestamp', 0)
    metrics = dict(num_downloaded_since_timestamp=(previous_count +
                   downloaded_uid_count),
                   current_download_queue_size=num_remaining_messages,
                   queue_checked_at=datetime.utcnow())

    saved_status.update_metrics(metrics)

    db_session.commit()

    log.info('mailsync progress', folder=folder_name,
             msg_queue_count=num_remaining_messages)
