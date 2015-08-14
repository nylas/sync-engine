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
| finish |      |    ^
----------      |    |_________________________
        ^       ∨                              |
        |   ----------------         ----------------------
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

from collections import namedtuple, OrderedDict
from datetime import datetime
from gevent import Greenlet, kill, spawn, sleep
import gevent.lock
from hashlib import sha256
from sqlalchemy import func
from sqlalchemy.orm import load_only
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound

from inbox.basicauth import ValidationError
from inbox.util.concurrency import retry_and_report_killed
from inbox.util.debug import bind_context
from inbox.util.itert import chunk
from inbox.util.misc import or_none
from inbox.util.threading import fetch_corresponding_thread, MAX_THREAD_LENGTH
from inbox.util.stats import statsd_client
from nylas.logging import get_logger
log = get_logger()
from inbox.crispin import connection_pool, retry_crispin, FolderMissingError
from inbox.models import Folder, Account, Message
from inbox.models.backends.imap import (ImapFolderSyncStatus, ImapThread,
                                        ImapUid, ImapFolderInfo)
from inbox.mailsync.exc import UidInvalid
from inbox.mailsync.backends.imap import common
from inbox.mailsync.backends.base import (MailsyncDone, mailsync_session_scope,
                                          THROTTLE_WAIT)
from inbox.heartbeat.store import HeartbeatStatusProxy
from inbox.events.ical import import_attached_events

GenericUIDMetadata = namedtuple('GenericUIDMetadata', 'throttled')


class UIDStack(object):
    """Container class for UIDs and metadata. Basically acts like a LIFO queue
    of key-value pairs, except that you can remove a specific key."""
    def __init__(self, *args):
        self._data = OrderedDict(*args)
        # Technically we really shouldn't need this, since no context-switch
        # should occur in member functions, but I really just don't want to
        # think about it so here's a semaphore.
        self._sem = gevent.lock.BoundedSemaphore(1)

    def empty(self):
        with self._sem:
            return not self._data

    def peekitem(self):
        with self._sem:
            k, v = self._data.popitem()
            self._data[k] = v
            return k, v

    def pop(self, k):
        with self._sem:
            return self._data.pop(k)

    def put(self, k, v):
        with self._sem:
            self._data[k] = v

    def keys(self):
        with self._sem:
            return self._data.keys()

    def __len__(self):
        with self._sem:
            return len(self._data)


class FolderSyncEngine(Greenlet):
    """Base class for a per-folder IMAP sync engine."""

    def __init__(self, account_id, folder_name, folder_id, email_address,
                 provider_name, poll_frequency, syncmanager_lock,
                 refresh_flags_max, retry_fail_classes):
        bind_context(self, 'foldersyncengine', account_id, folder_id)
        self.account_id = account_id
        self.folder_name = folder_name
        self.folder_id = folder_id
        self.poll_frequency = poll_frequency
        self.syncmanager_lock = syncmanager_lock
        self.refresh_flags_max = refresh_flags_max
        self.retry_fail_classes = retry_fail_classes
        self.state = None
        self.provider_name = provider_name

        # Metric flags for sync performance
        self.is_initial_sync = False
        self.is_first_sync = False
        self.is_first_message = False

        with mailsync_session_scope() as db_session:
            account = db_session.query(Account).get(self.account_id)
            self.throttled = account.throttled
            self.namespace_id = account.namespace.id
            assert self.namespace_id is not None, "namespace_id is None"

            folder = db_session.query(Folder).get(self.folder_id)
            if folder:
                self.is_initial_sync = folder.initial_sync_end is None
                self.is_first_sync = folder.initial_sync_start is None
                self.is_first_message = self.is_first_sync

        self.state_handlers = {
            'initial': self.initial_sync,
            'initial uidinvalid': self.resync_uids,
            'poll': self.poll,
            'poll uidinvalid': self.resync_uids,
            'finish': lambda self: 'finish',
        }

        Greenlet.__init__(self)

        self.heartbeat_status = HeartbeatStatusProxy(self.account_id,
                                                     self.folder_id,
                                                     self.folder_name,
                                                     email_address,
                                                     self.provider_name)

    def _run(self):
        # Bind greenlet-local logging context.
        self.log = log.new(account_id=self.account_id, folder=self.folder_name)
        # eagerly signal the sync status
        self.heartbeat_status.publish()
        return retry_and_report_killed(self._run_impl,
                                       account_id=self.account_id,
                                       folder_name=self.folder_name,
                                       logger=log,
                                       fail_classes=self.retry_fail_classes)

    def _run_impl(self):
        # We defer initializing the pool to here so that we'll retry if there
        # are any errors (remote server 503s or similar) when initializing it.
        self.conn_pool = connection_pool(self.account_id)
        try:
            saved_folder_status = self._load_state()
        except IntegrityError:
            # The state insert failed because the folder ID ForeignKey
            # was no longer valid, ie. the folder for this engine was deleted
            # while we were starting up.
            # Exit the sync and let the monitor sort things out.
            log.info("Folder state loading failed due to IntegrityError",
                     folder_id=self.folder_id, account_id=self.account_id)
            raise MailsyncDone()

        # NOTE: The parent ImapSyncMonitor handler could kill us at any
        # time if it receives a shutdown command. The shutdown command is
        # equivalent to ctrl-c.
        while True:
            old_state = self.state
            try:
                self.state = self.state_handlers[old_state]()
                self.heartbeat_status.publish(state=self.state)
            except UidInvalid:
                self.state = self.state + ' uidinvalid'
                self.heartbeat_status.publish(state=self.state)
            except FolderMissingError:
                # Folder was deleted by monitor while its sync was running.
                # TODO: Monitor should handle shutting down the folder engine.
                log.info('Folder disappeared. Stopping sync.',
                          account_id=self.account_id,
                          folder_name=self.folder_name,
                          folder_id=self.folder_id)
                raise MailsyncDone()
            except ValidationError as exc:
                log.error('Error authenticating; stopping sync', exc_info=True,
                          account_id=self.account_id, folder_id=self.folder_id,
                          logstash_tag='mark_invalid')
                with mailsync_session_scope() as db_session:
                    account = db_session.query(Account).get(self.account_id)
                    account.mark_invalid()
                    account.update_sync_error(str(exc))
                raise MailsyncDone()

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

    def set_stopped(self, db_session):
        saved_folder_status = db_session.query(ImapFolderSyncStatus)\
            .filter_by(account_id=self.account_id,
                       folder_id=self.folder_id).one()

        saved_folder_status.stop_sync()
        self.state = saved_folder_status.state

    def _report_initial_sync_start(self):
        with mailsync_session_scope() as db_session:
            q = db_session.query(Folder).get(self.folder_id)
            q.initial_sync_start = datetime.utcnow()

    def _report_initial_sync_end(self):
        with mailsync_session_scope() as db_session:
            q = db_session.query(Folder).get(self.folder_id)
            q.initial_sync_end = datetime.utcnow()

    @retry_crispin
    def initial_sync(self):
        log.bind(state='initial')
        log.info('starting initial sync')

        if self.is_first_sync:
            self._report_initial_sync_start()
            self.is_first_sync = False

        with self.conn_pool.get() as crispin_client:
            crispin_client.select_folder(self.folder_name, uidvalidity_cb)
            self.initial_sync_impl(crispin_client)

        if self.is_initial_sync:
            self._report_initial_sync_end()
            self.is_initial_sync = False

        return 'poll'

    @retry_crispin
    def poll(self):
        log.bind(state='poll')
        log.info('polling')
        self.poll_impl()
        return 'poll'

    @retry_crispin
    def resync_uids(self):
        log.bind(state=self.state)
        log.info('UIDVALIDITY changed')
        self.resync_uids_impl()
        return 'initial'

    def initial_sync_impl(self, crispin_client):
        # We wrap the block in a try/finally because the change_poller greenlet
        # needs to be killed when this greenlet is interrupted
        change_poller = None
        try:
            assert crispin_client.selected_folder_name == self.folder_name
            remote_uids = crispin_client.all_uids()
            with self.syncmanager_lock:
                with mailsync_session_scope() as db_session:
                    local_uids = common.all_uids(self.account_id, db_session,
                                                 self.folder_id)
                    self.remove_deleted_uids(db_session, local_uids,
                                             remote_uids)

            new_uids = set(remote_uids) - local_uids
            download_stack = UIDStack()
            for uid in sorted(new_uids):
                download_stack.put(uid, GenericUIDMetadata(self.throttled))

            with mailsync_session_scope() as db_session:
                self.update_uid_counts(
                    db_session,
                    remote_uid_count=len(remote_uids),
                    # This is the initial size of our download_queue
                    download_uid_count=len(new_uids))

            change_poller = spawn(self.poll_for_changes, download_stack)
            bind_context(change_poller, 'changepoller', self.account_id,
                         self.folder_id)
            self.download_uids(crispin_client, download_stack)

        finally:
            if change_poller is not None:
                # schedule change_poller to die
                kill(change_poller)

    def poll_impl(self):
        with self.conn_pool.get() as crispin_client:
            crispin_client.select_folder(self.folder_name, uidvalidity_cb)
            download_stack = UIDStack()
            self.check_uid_changes(crispin_client, download_stack,
                                   async_download=False)
        sleep(self.poll_frequency)

    def resync_uids_impl(self):
        # NOTE: first, let's check if the UIVDALIDITY change was spurious, if
        # it is, just discard it and go on, if it isn't, drop the relevant
        # entries (filtering by account and folder IDs) from the imapuid table,
        # download messages, if necessary - in case a message has changed UID -
        # update UIDs, and discard orphaned messages. -siro
        with mailsync_session_scope() as db_session:
            account = db_session.query(Account).get(self.account_id)
            folder_info = db_session.query(ImapFolderInfo). \
                filter_by(account_id=self.account_id,
                          folder_id=self.folder_id).one()
            cached_uidvalidity = folder_info.uidvalidity
            with self.conn_pool.get() as crispin_client:
                crispin_client.select_folder(self.folder_name,
                                             lambda *args: True)
                uidvalidity = crispin_client.selected_uidvalidity
                if uidvalidity <= cached_uidvalidity:
                    log.debug('UIDVALIDITY unchanged')
                    return
                invalid_uids = db_session.query(ImapUid). \
                    filter_by(account_id=self.account_id,
                              folder_id=self.folder_id)
                data_sha256_message = {uid.message.data_sha256: uid.message
                                       for uid in invalid_uids}
                for uid in invalid_uids:
                    db_session.delete(uid)
                # NOTE: this is necessary (and OK since it doesn't persist any
                # data) to maintain the order between UIDs deletion and
                # insertion. Without this, I was seeing constraints violation
                # on the imapuid table. -siro
                db_session.flush()
                remote_uids = crispin_client.all_uids()
                for remote_uid in remote_uids:
                    raw_message = crispin_client.uids([remote_uid])[0]
                    data_sha256 = sha256(raw_message.body).hexdigest()
                    if data_sha256 in data_sha256_message:
                        message = data_sha256_message[data_sha256]

                        # Create a new imapuid
                        uid = ImapUid(msg_uid=raw_message.uid,
                                      message=message,
                                      account_id=self.account_id,
                                      folder_id=self.folder_id)
                        uid.update_flags(raw_message.flags)
                        db_session.add(uid)

                        # Update the existing message's metadata too
                        common.update_message_metadata(db_session, account,
                                                       message, uid.is_draft)

                        del data_sha256_message[data_sha256]
                    else:
                        self.download_and_commit_uids(crispin_client,
                                                      [remote_uid])
                    self.heartbeat_status.publish()
                    # FIXME: do we want to throttle the account when recovering
                    # from UIDVALIDITY changes? -siro
            for message in data_sha256_message.itervalues():
                db_session.delete(message)
            folder_info.uidvalidity = uidvalidity
            folder_info.highestmodseq = None

    @retry_crispin
    def poll_for_changes(self, download_stack):
        while True:
            with self.conn_pool.get() as crispin_client:
                crispin_client.select_folder(self.folder_name, uidvalidity_cb)
                self.check_uid_changes(crispin_client, download_stack,
                                       async_download=True)
            sleep(self.poll_frequency)

    def download_uids(self, crispin_client, download_stack):
        while not download_stack.empty():
            uid, metadata = download_stack.peekitem()
            self.download_and_commit_uids(crispin_client, [uid])
            download_stack.pop(uid)
            report_progress(self.account_id, self.folder_name, 1,
                            len(download_stack))
            self.heartbeat_status.publish()
            if self.throttled and metadata is not None and metadata.throttled:
                # Check to see if the account's throttled state has been
                # modified. If so, immediately accelerate.
                with mailsync_session_scope() as db_session:
                    acc = db_session.query(Account).get(self.account_id)
                    self.throttled = acc.throttled
                if self.throttled:
                    log.debug('throttled; sleeping')
                    sleep(THROTTLE_WAIT)

    def create_message(self, db_session, acct, folder, msg):
        assert acct is not None and acct.namespace is not None

        # Check if we somehow already saved the imapuid (shouldn't happen, but
        # possible due to race condition). If so, don't commit changes.
        existing_imapuid = db_session.query(ImapUid).filter(
            ImapUid.account_id == acct.id, ImapUid.folder_id == folder.id,
            ImapUid.msg_uid == msg.uid).first()
        if existing_imapuid is not None:
            log.error('Expected to create imapuid, but existing row found',
                      remote_msg_uid=msg.uid,
                      existing_imapuid=existing_imapuid.id)
            return None

        new_uid = common.create_imap_message(db_session, log, acct, folder,
                                             msg)
        new_uid = self.add_message_attrs(db_session, new_uid, msg)

        # We're calling import_attached_events here instead of some more
        # obvious place (like Message.create_from_synced) because the function
        # requires new_uid.message to have been flushed.
        # This is necessary because the import_attached_events does db lookups.
        if new_uid.message.has_attached_events:
            with db_session.no_autoflush:
                import_attached_events(db_session, acct, new_uid.message)

        # If we're in the polling state, then we want to report the metric
        # for latency when the message was received vs created
        if self.state == 'poll':
            latency_millis = (
                datetime.utcnow() - new_uid.message.received_date) \
                .total_seconds() * 1000
            metrics = [
                '.'.join(['accounts', 'overall', 'message_latency']),
                '.'.join(['accounts', str(acct.id), 'message_latency']),
                '.'.join(['providers', self.provider_name, 'message_latency']),
            ]
            for metric in metrics:
                statsd_client.timing(metric, latency_millis)

        return new_uid

    def _count_thread_messages(self, thread_id, db_session):
        count, = db_session.query(func.count(Message.id)). \
            filter(Message.thread_id == thread_id).one()
        return count

    def add_message_attrs(self, db_session, new_uid, msg):
        """ Post-create-message bits."""
        with db_session.no_autoflush:
            parent_thread = fetch_corresponding_thread(
                db_session, self.namespace_id, new_uid.message)
            construct_new_thread = True

            if parent_thread:
                # If there's a parent thread that isn't too long already,
                # add to it. Otherwise create a new thread.
                parent_message_count = self._count_thread_messages(
                    parent_thread.id, db_session)
                if parent_message_count < MAX_THREAD_LENGTH:
                    construct_new_thread = False

            if construct_new_thread:
                new_uid.message.thread = ImapThread.from_imap_message(
                    db_session, new_uid.account.namespace, new_uid.message)
            else:
                parent_thread.messages.append(new_uid.message)

        db_session.flush()
        return new_uid

    def remove_deleted_uids(self, db_session, local_uids, remote_uids):
        """
        Remove imapuid entries that no longer exist on the remote.

        Works as follows:
            1. Do a LIST on the current folder to see what messages are on the
                server.
            2. Compare to message uids stored locally.
            3. Purge uids we have locally but not on the server. Ignore
               remote uids that aren't saved locally.

        Make SURE to be holding `syncmanager_lock` when calling this function;
        we do not grab it here to allow callers to lock higher level
        functionality.

        """
        to_delete = set(local_uids) - set(remote_uids)
        common.remove_deleted_uids(self.account_id, db_session, to_delete,
                                   self.folder_id)

    def download_and_commit_uids(self, crispin_client, uids):
        start = datetime.utcnow()
        raw_messages = crispin_client.uids(uids)
        if not raw_messages:
            return 0

        new_uids = set()
        with self.syncmanager_lock:
            # there is the possibility that another green thread has already
            # downloaded some message(s) from this batch... check within the
            # lock
            with mailsync_session_scope() as db_session:
                account = db_session.query(Account).get(self.account_id)
                folder = db_session.query(Folder).get(self.folder_id)
                for msg in raw_messages:
                    uid = self.create_message(db_session, account, folder,
                                              msg)
                    if uid is not None:
                        db_session.add(uid)
                        db_session.flush()
                        new_uids.add(uid)
                db_session.commit()

        # If we downloaded uids, record message velocity (#uid / latency)
        if self.state == 'initial' and len(new_uids):
            self._report_message_velocity(datetime.utcnow() - start,
                                          len(new_uids))
        if self.is_first_message:
            self._report_first_message()
            self.is_first_message = False

        return len(new_uids)

    def _report_first_message(self):
        now = datetime.utcnow()

        with mailsync_session_scope() as db_session:
            account = db_session.query(Account).get(self.account_id)
            account_created = account.created_at

        latency = (now - account_created).total_seconds() * 1000
        metrics = [
            '.'.join(['providers', self.provider_name, 'first_message']),
            '.'.join(['providers', 'overall', 'first_message'])
        ]

        for metric in metrics:
            statsd_client.timing(metric, latency)

    def _report_message_velocity(self, timedelta, num_uids):
        latency = (timedelta).total_seconds() * 1000
        latency_per_uid = float(latency) / num_uids
        metrics = [
            '.'.join(['providers', self.provider_name,
                      'message_velocity']),
            '.'.join(['providers', 'overall', 'message_velocity'])
        ]
        for metric in metrics:
            statsd_client.timing(metric, latency_per_uid)

    def update_metadata(self, crispin_client, updated):
        """ Update flags (the only metadata that can change). """
        # bigger chunk because the data being fetched here is very small
        for uids in chunk(updated, 5 * crispin_client.CHUNK_SIZE):
            new_flags = crispin_client.flags(uids)
            # Messages can disappear in the meantime; we'll update them next
            # sync.
            uids = [uid for uid in uids if uid in new_flags]
            with self.syncmanager_lock:
                with mailsync_session_scope() as db_session:
                    common.update_metadata(self.account_id, db_session,
                                           self.folder_name, self.folder_id,
                                           uids, new_flags)
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

    def check_uid_changes(self, crispin_client, download_stack,
                          async_download):
        remote_uids = set(crispin_client.all_uids())
        with self.syncmanager_lock:
            with mailsync_session_scope() as db_session:
                local_uids = common.all_uids(self.account_id, db_session,
                                             self.folder_id)
                # Download new UIDs.
                stack_uids = set(download_stack.keys())
                local_with_pending_uids = local_uids | stack_uids
                for uid in sorted(remote_uids):
                    if uid not in local_with_pending_uids:
                        download_stack.put(uid, None)
                self.remove_deleted_uids(db_session, local_uids, remote_uids)
        if not async_download:
            self.download_uids(crispin_client, download_stack)
            with mailsync_session_scope() as db_session:
                self.update_uid_counts(
                    db_session,
                    remote_uid_count=len(remote_uids),
                    download_uid_count=len(download_stack))
        to_refresh = sorted(remote_uids &
                            local_uids)[-self.refresh_flags_max:]
        self.update_metadata(crispin_client, to_refresh)
        with mailsync_session_scope() as db_session:
            common.update_folder_info(self.account_id, db_session,
                                      self.folder_name,
                                      crispin_client.selected_uidvalidity,
                                      None,
                                      crispin_client.selected_uidnext)


def uidvalidity_cb(account_id, folder_name, select_info):
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
                'cached uidvalidity: {}'.format(folder_name.encode('utf-8'),
                                                selected_uidvalidity,
                                                saved_uidvalidity))
    return select_info


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

    statsd_client.gauge(
        ".".join(["accounts", str(account_id), "messages_downloaded"]),
        metrics.get("num_downloaded_since_timestamp"))
