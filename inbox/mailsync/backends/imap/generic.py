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

--------------
SESSION SCOPES
--------------

Database sessions are held for as short a duration as possible---just to
query for needed information or update the local state. Long-held database
sessions reduce scalability.

"""
from __future__ import division

from datetime import datetime

from gevent import Greenlet, spawn, sleep
from gevent.queue import LifoQueue
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm import load_only

from inbox.util.concurrency import retry_and_report_killed
from inbox.util.itert import chunk
from inbox.util.misc import or_none
from inbox.util.threading import cleanup_subject, thread_messages
from inbox.log import get_logger
log = get_logger()
from inbox.crispin import connection_pool, retry_crispin
from inbox.models.session import session_scope
from inbox.models import Folder
from inbox.models.backends.imap import ImapFolderSyncStatus, ImapThread
from inbox.models.util import reconcile_message
from inbox.mailsync.exc import UidInvalid
from inbox.mailsync.reporting import report_stopped
from inbox.mailsync.backends.imap import common
from inbox.mailsync.backends.base import (create_db_objects,
                                          commit_uids, MailsyncDone,
                                          mailsync_session_scope)


def _pool(account_id):
    """ Get a crispin pool, throwing an error if it's invalid."""
    pool = connection_pool(account_id)
    if not pool.valid:
        raise MailsyncDone()
    return pool


class FolderSyncEngine(Greenlet):
    """Base class for a per-folder IMAP sync engine."""

    def __init__(self, account_id, folder_name, folder_id, email_address,
                 provider_name, poll_frequency, syncmanager_lock,
                 refresh_flags_max, retry_fail_classes):
        self.account_id = account_id
        self.folder_name = folder_name
        self.folder_id = folder_id
        self.poll_frequency = poll_frequency
        self.syncmanager_lock = syncmanager_lock
        self.refresh_flags_max = refresh_flags_max
        self.retry_fail_classes = retry_fail_classes
        self.state = None
        self.conn_pool = _pool(self.account_id)

        self.state_handlers = {
            'initial': self.initial_sync,
            'initial uidinvalid': self.resync_uids_from('initial'),
            'poll': self.poll,
            'poll uidinvalid': self.resync_uids_from('poll'),
            'finish': lambda self: 'finish',
        }

        Greenlet.__init__(self)
        self.link_value(lambda _: report_stopped(account_id=self.account_id,
                                                 folder_name=self.folder_name))

    def _run(self):
        # Bind greenlet-local logging context.
        log.new(account_id=self.account_id, folder=self.folder_name)
        return retry_and_report_killed(self._run_impl,
                                       account_id=self.account_id,
                                       folder_name=self.folder_name,
                                       logger=log,
                                       fail_classes=self.retry_fail_classes)

    def _run_impl(self):
        # We do NOT ignore soft deletes in the mail sync because it gets real
        # complicated handling e.g. when backends reuse imapids. ImapUid
        # objects are the only objects deleted by the mail sync backends
        # anyway.
        saved_folder_status = self._load_state()
        # NOTE: The parent ImapSyncMonitor handler could kill us at any
        # time if it receives a shutdown command. The shutdown command is
        # equivalent to ctrl-c.
        while True:
            old_state = self.state
            try:
                self.state = self.state_handlers[old_state]()
            except UidInvalid:
                self.state = self.state + ' uidinvalid'
            # State handlers are idempotent, so it's okay if we're
            # killed between the end of the handler and the commit.
            if self.state != old_state:
                # Don't need to re-query, will auto refresh on re-associate.
                with mailsync_session_scope() as db_session:
                    db_session.add(saved_folder_status)
                    saved_folder_status.state = self.state
                    db_session.commit()
            if self.state == 'finish':
                return

    def _load_state(self):
        with mailsync_session_scope() as db_session:
            try:
                state = ImapFolderSyncStatus.state
                saved_folder_status = db_session.query(ImapFolderSyncStatus)\
                    .filter_by(account_id=self.account_id,
                               folder_id=self.folder_id).options(
                        load_only(state)).one()
            except NoResultFound:
                saved_folder_status = ImapFolderSyncStatus(
                    account_id=self.account_id, folder_id=self.folder_id)
                db_session.add(saved_folder_status)

            saved_folder_status.start_sync()
            db_session.commit()
            self.state = saved_folder_status.state
            return saved_folder_status

    @retry_crispin
    def initial_sync(self):
        with self.conn_pool.get() as crispin_client:
            uid_download_stack = LifoQueue()
            crispin_client.select_folder(
                self.folder_name, uidvalidity_cb(crispin_client.account_id))

            with mailsync_session_scope() as db_session:
                local_uids = common.all_uids(crispin_client.account_id,
                                             db_session, self.folder_name)

            self.initial_sync_impl(crispin_client, local_uids,
                                   uid_download_stack)
        return 'poll'

    @retry_crispin
    def poll(self):
        with self.conn_pool.get() as crispin_client:
            self.poll_impl(crispin_client)
            return 'poll'

    def resync_uids_from(self, previous_state):
        @retry_crispin
        def resync_uids(self):
            """ Call this when UIDVALIDITY is invalid to fix up the database.

            What happens here is we fetch new UIDs from the IMAP server and
            match them with X-GM-MSGIDs and sub in the new UIDs for the old. No
            messages are re-downloaded.
            """
            log.error("UIDVALIDITY changed")
            raise NotImplementedError
            return previous_state
        return resync_uids

    def initial_sync_impl(self, crispin_client, local_uids,
                          uid_download_stack,
                          spawn_flags_refresh_poller=True):
        # We wrap the block in a try/finally because the greenlets like
        # new_uid_poller need to be killed when this greenlet is interrupted
        new_uid_poller, flags_refresh_poller = None, None
        try:
            assert crispin_client.selected_folder_name == self.folder_name

            remote_uids = crispin_client.all_uids()
            log.info(remote_uid_count=len(remote_uids))
            log.info(local_uid_count=len(local_uids))

            with self.syncmanager_lock:
                log.debug("imap_initial_sync acquired syncmanager_lock")
                with mailsync_session_scope() as db_session:
                    deleted_uids = self.remove_deleted_uids(
                        db_session, local_uids, remote_uids)

            local_uids = set(local_uids) - deleted_uids

            new_uids = set(remote_uids) - local_uids
            add_uids_to_stack(new_uids, uid_download_stack)

            with mailsync_session_scope() as db_session:
                self.update_uid_counts(
                    db_session,
                    remote_uid_count=len(remote_uids),
                    # This is the initial size of our download_queue
                    download_uid_count=len(new_uids),
                    # Flags are updated in __imap_flag_change_poller() and
                    # update_uid_count is set there
                    delete_uid_count=len(deleted_uids))

            new_uid_poller = spawn(self.check_new_uids, uid_download_stack)

            if spawn_flags_refresh_poller:
                flags_refresh_poller = spawn(self.__imap_flag_change_poller)

            self.download_uids(crispin_client, uid_download_stack)

        finally:
            if new_uid_poller is not None:
                new_uid_poller.kill()

            if spawn_flags_refresh_poller and flags_refresh_poller is not None:
                flags_refresh_poller.kill()

    def poll_impl(self, crispin_client):
        crispin_client.select_folder(self.folder_name,
                                     uidvalidity_cb(self.account_id))

        remote_uids = set(crispin_client.all_uids())
        with mailsync_session_scope() as db_session:
            local_uids = common.all_uids(
                self.account_id, db_session, self.folder_name)
            deleted_uids = self.remove_deleted_uids(
                db_session, local_uids, remote_uids)

            local_uids -= deleted_uids
            log.info("Removed {} deleted UIDs from {}".format(
                len(deleted_uids), self.folder_name))
            uids_to_download = remote_uids - local_uids

            self.update_uid_counts(db_session,
                                   remote_uid_count=len(remote_uids),
                                   download_uid_count=len(uids_to_download),
                                   delete_uid_count=len(deleted_uids))

        log.info("UIDs to download: {}".format(uids_to_download))
        if uids_to_download:
            self.download_uids(crispin_client,
                               uid_list_to_stack(uids_to_download))

        uids_to_refresh = sorted(remote_uids -
                                 uids_to_download)[-self.refresh_flags_max:]
        log.info('UIDs to refresh: ', uids=uids_to_refresh)
        if uids_to_refresh:
            self.update_metadata(crispin_client, uids_to_refresh)

        sleep(self.poll_frequency)

    # TODO(emfree): figure out better names for this and the function that
    # it wraps.
    def download_uids(self, crispin_client, uid_download_stack):
        while not uid_download_stack.empty():
            # Defer removing UID from queue until after it's committed to the
            # DB' to avoid races with check_new_uids() XXX this should be
            # uid_download_stack.peek_nowait(), which is currently buggy in
            # gevent (patch pending)
            uid = uid_download_stack.queue[-1]
            self.download_and_commit_uids(crispin_client, self.folder_name,
                                          [uid])
            uid_download_stack.get_nowait()
            report_progress(self.account_id, self.folder_name, 1,
                            uid_download_stack.qsize())

        log.info('saved all messages and metadata',
                 new_uidvalidity=crispin_client.selected_uidvalidity)

    def create_message(self, db_session, acct, folder, msg):
        assert acct is not None and acct.namespace is not None

        new_uid = common.create_imap_message(db_session, log, acct, folder,
                                             msg)

        new_uid = self.add_message_attrs(db_session, new_uid, msg, folder)
        return new_uid

    def add_message_attrs(self, db_session, new_uid, msg, folder):
        """ Post-create-message bits."""
        with db_session.no_autoflush:
            clean_subject = cleanup_subject(new_uid.message.subject)
            parent_threads = db_session.query(ImapThread).filter(
                ImapThread.subject.like(clean_subject)).all()

            if parent_threads == []:
                new_uid.message.thread = ImapThread.from_imap_message(
                    db_session, new_uid.account.namespace, new_uid.message)
                new_uid.message.thread_order = 0
            else:
                # FIXME: arbitrarily select the first thread. This shouldn't
                # be a problem now but it could become one if we choose
                # to implement thread-splitting.
                parent_thread = parent_threads[0]
                parent_thread.messages.append(new_uid.message)
                constructed_thread = thread_messages(parent_thread.messages)
                for index, message in enumerate(constructed_thread):
                    message.thread_order = index

            # FIXME: refactor 'new_labels' name. This is generic IMAP, not
            # gmail.
            # make sure this thread has all the correct labels
            new_labels = common.update_thread_labels(new_uid.message.thread,
                                                     folder.name,
                                                     [folder.canonical_name],
                                                     db_session)

            # Reconciliation for Drafts, Sent Mail folders:
            if (('draft' in new_labels or 'sent' in new_labels) and not
                    msg.created and new_uid.message.inbox_uid):
                reconcile_message(db_session, new_uid.message.inbox_uid,
                                  new_uid.message)

            new_uid.update_imap_flags(msg.flags)

            return new_uid

    def remove_deleted_uids(self, db_session, local_uids, remote_uids):
        """ Remove imapuid entries that no longer exist on the remote.

        Works as follows:
            1. Do a LIST on the current folder to see what messages are on the
                server.
            2. Compare to message uids stored locally.
            3. Purge messages we have locally but not on the server. Ignore
                messages we have on the server that aren't local.

        Make SURE to be holding `syncmanager_lock` when calling this function;
        we do not grab it here to allow callers to lock higher level
        functionality.  """
        if len(remote_uids) > 0 and len(local_uids) > 0:
            for elt in remote_uids:
                assert not isinstance(elt, str)

        to_delete = set(local_uids) - set(remote_uids)
        if to_delete:
            common.remove_messages(self.account_id, db_session, to_delete,
                                   self.folder_name)
            log.info('deleted removed messages', count=len(to_delete))

        return to_delete

    def download_and_commit_uids(self, crispin_client, folder_name, uids):
        # Note that folder_name here might *NOT* be equal to self.folder_name,
        # because, for example, we download messages via the 'All Mail' folder
        # in Gmail.
        raw_messages = safe_download(crispin_client, uids)
        with self.syncmanager_lock:
            with mailsync_session_scope() as db_session:
                new_imapuids = create_db_objects(
                    self.account_id, db_session, log, folder_name,
                    raw_messages, self.create_message)
                commit_uids(db_session, log, new_imapuids)
        return len(new_imapuids)

    def update_metadata(self, crispin_client, updated):
        """ Update flags (the only metadata that can change). """

        # bigger chunk because the data being fetched here is very small
        for uids in chunk(updated, 5 * crispin_client.CHUNK_SIZE):
            new_flags = crispin_client.flags(uids)
            # Messages can disappear in the meantime; we'll update them next
            # sync.
            uids = [uid for uid in uids if uid in new_flags]
            log.info("new flags ", new_flags=new_flags,
                     folder_name=self.folder_name)
            with self.syncmanager_lock:
                with mailsync_session_scope() as db_session:
                    common.update_metadata(self.account_id, db_session,
                                           self.folder_name, uids,
                                           new_flags)
                    db_session.commit()

    def update_uid_counts(self, db_session, **kwargs):
        saved_status = db_session.query(ImapFolderSyncStatus).join(Folder). \
            filter(ImapFolderSyncStatus.account_id == self.account_id,
                   Folder.name == self.folder_name).one()
        # We're not updating the current_remote_count metric
        # so don't update uid_checked_timestamp.
        if kwargs.get('remote_uid_count') is None:
            saved_status.update_metrics(kwargs)
        else:
            metrics = dict(uid_checked_timestamp=datetime.utcnow())
            metrics.update(kwargs)
            saved_status.update_metrics(metrics)
        db_session.commit()

    def __imap_flag_change_poller(self):
        """
        Periodically update message flags for those servers
        who don't support CONDSTORE.
        Runs until killed. (Intended to be run in a greenlet)
        """
        log.info("Spinning up new flags-refresher for ",
                 folder_name=self.folder_name)
        with self.conn_pool.get() as crispin_client:
            with mailsync_session_scope() as db_session:
                crispin_client.select_folder(self.folder_name,
                                             uidvalidity_cb(
                                                 crispin_client.account_id))
            while True:
                remote_uids = set(crispin_client.all_uids())
                local_uids = common.all_uids(self.account_id, db_session,
                                             self.folder_name)
                # STOPSHIP(emfree): sorted does nothing here
                to_refresh = sorted(remote_uids &
                                    local_uids)[-self.refresh_flags_max:]

                self.update_metadata(crispin_client, to_refresh)
                with session_scope(ignore_soft_deletes=True) as db_session:
                    self.update_uid_counts(db_session,
                                           update_uid_count=len(to_refresh))

                sleep(self.poll_frequency)

    def check_new_uids(self, uid_download_stack):
        """ Check for new UIDs and add them to the download stack.

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
        log.info("starting new UID-check poller")
        with self.conn_pool.get() as crispin_client:
            crispin_client.select_folder(
                self.folder_name, uidvalidity_cb(crispin_client.account_id))
            while True:
                remote_uids = set(crispin_client.all_uids())
                # We lock this section to make sure no messages are being
                # created while we make sure the queue is in a good state.
                with self.syncmanager_lock:
                    with mailsync_session_scope() as db_session:
                        local_uids = common.all_uids(self.account_id,
                                                     db_session,
                                                     self.folder_name)
                        stack_uids = set(uid_download_stack.queue)
                        local_with_pending_uids = local_uids | stack_uids
                        deleted_uids = self.remove_deleted_uids(
                            db_session, local_uids, remote_uids)
                        log.info('remoted deleted uids',
                                 count=len(deleted_uids))

                        # filter out messages that have disappeared on the
                        # remote side
                        new_uid_download_stack = {
                            u for u in uid_download_stack.queue if u in
                            remote_uids}

                        # add in any new uids from the remote
                        for uid in remote_uids:
                            if uid not in local_with_pending_uids:
                                new_uid_download_stack.add(uid)
                        uid_download_stack.queue = sorted(
                            new_uid_download_stack, key=int)

                        self.update_uid_counts(
                            db_session,
                            remote_uid_count=len(remote_uids),
                            download_uid_count=uid_download_stack.qsize(),
                            delete_uid_count=len(deleted_uids))
                sleep(self.poll_frequency)


def uid_list_to_stack(uids):
    """ UID download function needs a stack even for polling. """
    uid_download_stack = LifoQueue()
    for uid in sorted(uids, key=int):
        uid_download_stack.put(uid)
    return uid_download_stack


def uidvalidity_cb(account_id):
    def fn(folder_name, select_info):
        assert folder_name is not None and select_info is not None, \
            "must start IMAP session before verifying UIDVALIDITY"
        with mailsync_session_scope() as db_session:
            saved_folder_info = common.get_folder_info(account_id, db_session,
                                                       folder_name)
            saved_uidvalidity = or_none(saved_folder_info, lambda i:
                                        i.uidvalidity)
        selected_uidvalidity = select_info['UIDVALIDITY']

        if saved_folder_info:
            is_valid = common.uidvalidity_valid(account_id,
                                                selected_uidvalidity,
                                                folder_name, saved_uidvalidity)
            if not is_valid:
                raise UidInvalid(
                    'folder: {}, remote uidvalidity: {}, '
                    'cached uidvalidity: {}'.format(
                        folder_name, selected_uidvalidity, saved_uidvalidity))
        return select_info
    return fn


def add_uids_to_stack(uids, uid_download_stack):
    for uid in sorted(uids, key=int):
        uid_download_stack.put(uid)


def safe_download(crispin_client, uids):
    try:
        raw_messages = crispin_client.uids(uids)
    except MemoryError, e:
        log.error('ran out of memory while fetching UIDs', uids=uids)
        raise e

    return raw_messages


def report_progress(account_id, folder_name, downloaded_uid_count,
                    num_remaining_messages):
    """ Inform listeners of sync progress. """

    with mailsync_session_scope() as db_session:
        saved_status = db_session.query(ImapFolderSyncStatus).join(Folder)\
            .filter(
                ImapFolderSyncStatus.account_id == account_id,
                Folder.name == folder_name).one()

        previous_count = saved_status.metrics.get(
            'num_downloaded_since_timestamp', 0)

        metrics = dict(num_downloaded_since_timestamp=(previous_count +
                                                       downloaded_uid_count),
                       download_uid_count=num_remaining_messages,
                       queue_checked_at=datetime.utcnow())

        saved_status.update_metrics(metrics)
        db_session.commit()
