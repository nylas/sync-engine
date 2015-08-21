# deal with unicode literals: http://www.python.org/dev/peps/pep-0263/
# vim: set fileencoding=utf-8 :
"""
----------------
IMAP SYNC ENGINE
----------------

Okay, here's the deal.

The IMAP sync engine runs per-folder on each account.

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

from datetime import datetime, timedelta
from gevent import Greenlet, kill, spawn, sleep
from hashlib import sha256
from sqlalchemy import func
from sqlalchemy.orm import load_only
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound

from inbox.basicauth import ValidationError
from inbox.util.concurrency import retry_and_report_killed
from inbox.util.debug import bind_context
from inbox.util.misc import or_none
from inbox.util.threading import fetch_corresponding_thread, MAX_THREAD_LENGTH
from inbox.util.stats import statsd_client
from nylas.logging import get_logger
log = get_logger()
from inbox.crispin import connection_pool, retry_crispin, FolderMissingError
from inbox.models import Folder, Account, Message
from inbox.models.backends.imap import (ImapFolderSyncStatus, ImapThread,
                                        ImapUid, ImapFolderInfo)
from inbox.models.session import session_scope
from inbox.mailsync.exc import UidInvalid
from inbox.mailsync.backends.imap import common
from inbox.mailsync.backends.base import MailsyncDone
from inbox.heartbeat.store import HeartbeatStatusProxy
from inbox.events.ical import import_attached_events


# Idle doesn't necessarily pick up flag changes, so we don't want to
# idle for very long, or we won't detect things like messages being
# marked as read.
IDLE_WAIT = 30
DEFAULT_POLL_FREQUENCY = 30
# Poll on the Inbox folder more often.
INBOX_POLL_FREQUENCY = 10
FAST_FLAGS_REFRESH_LIMIT = 100
SLOW_FLAGS_REFRESH_LIMIT = 2000
SLOW_REFRESH_INTERVAL = timedelta(seconds=3600)
FAST_REFRESH_INTERVAL = timedelta(seconds=30)


class FolderSyncEngine(Greenlet):
    """Base class for a per-folder IMAP sync engine."""
    def __init__(self, account_id, folder_name, folder_id, email_address,
                 provider_name, syncmanager_lock):
        bind_context(self, 'foldersyncengine', account_id, folder_id)
        self.account_id = account_id
        self.folder_name = folder_name
        self.folder_id = folder_id
        if self.folder_name.lower() == 'inbox':
            self.poll_frequency = INBOX_POLL_FREQUENCY
        else:
            self.poll_frequency = DEFAULT_POLL_FREQUENCY
        self.syncmanager_lock = syncmanager_lock
        self.state = None
        self.provider_name = provider_name
        self.last_fast_refresh = None
        self.conn_pool = connection_pool(self.account_id)

        # Metric flags for sync performance
        self.is_initial_sync = False
        self.is_first_sync = False
        self.is_first_message = False

        with session_scope() as db_session:
            account = Account.get(self.account_id, db_session)
            self.namespace_id = account.namespace.id
            assert self.namespace_id is not None, "namespace_id is None"

            folder = Folder.get(self.folder_id, db_session)
            if folder:
                self.is_initial_sync = folder.initial_sync_end is None
                self.is_first_sync = folder.initial_sync_start is None
                self.is_first_message = self.is_first_sync

        self.state_handlers = {
            'initial': self.initial_sync,
            'initial uidinvalid': self.resync_uids,
            'poll': self.poll,
            'poll uidinvalid': self.resync_uids,
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
                                       logger=log)

    def _run_impl(self):
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
                with session_scope() as db_session:
                    account = db_session.query(Account).get(self.account_id)
                    account.mark_invalid()
                    account.update_sync_error(str(exc))
                raise MailsyncDone()

            # State handlers are idempotent, so it's okay if we're
            # killed between the end of the handler and the commit.
            if self.state != old_state:
                # Don't need to re-query, will auto refresh on re-associate.
                with session_scope() as db_session:
                    db_session.add(saved_folder_status)
                    saved_folder_status.state = self.state
                    db_session.commit()

    def _load_state(self):
        with session_scope() as db_session:
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
        with session_scope() as db_session:
            q = db_session.query(Folder).get(self.folder_id)
            q.initial_sync_start = datetime.utcnow()

    def _report_initial_sync_end(self):
        with session_scope() as db_session:
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
            # Ensure we have an ImapFolderInfo row created prior to sync start.
            with session_scope() as db_session:
                try:
                    db_session.query(ImapFolderInfo). \
                        filter(ImapFolderInfo.account_id == self.account_id,
                               ImapFolderInfo.folder_id == self.folder_id). \
                        one()
                except NoResultFound:
                    imapfolderinfo = ImapFolderInfo(
                        account_id=self.account_id, folder_id=self.folder_id,
                        uidvalidity=crispin_client.selected_uidvalidity,
                        uidnext=crispin_client.selected_uidnext)
                    db_session.add(imapfolderinfo)
                db_session.commit()

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
                with session_scope() as db_session:
                    local_uids = common.local_uids(self.account_id, db_session,
                                                   self.folder_id)
                    common.remove_deleted_uids(
                        self.account_id, self.folder_id,
                        set(local_uids).difference(remote_uids),
                        db_session)

            new_uids = set(remote_uids).difference(local_uids)
            with session_scope() as db_session:
                self.update_uid_counts(
                    db_session,
                    remote_uid_count=len(remote_uids),
                    # This is the initial size of our download_queue
                    download_uid_count=len(new_uids))

            change_poller = spawn(self.poll_for_changes)
            bind_context(change_poller, 'changepoller', self.account_id,
                         self.folder_id)
            uids = sorted(new_uids, reverse=True)
            for uid in uids:
                # The speedup from batching appears to be less clear for
                # non-Gmail accounts, so for now just download one-at-a-time.
                self.download_and_commit_uids(crispin_client, [uid])
                self.heartbeat_status.publish()

        finally:
            if change_poller is not None:
                # schedule change_poller to die
                kill(change_poller)

    def should_idle(self, crispin_client):
        return (crispin_client.idle_supported() and
                self.folder_name in crispin_client.folder_names()['inbox'])

    def poll_impl(self):
        with self.conn_pool.get() as crispin_client:
            self.check_uid_changes(crispin_client)
            if self.should_idle(crispin_client):
                crispin_client.select_folder(self.folder_name,
                                             self.uidvalidity_cb)
                idling = True
                crispin_client.idle(IDLE_WAIT)
            else:
                idling = False
        # Close IMAP connection before sleeping
        if not idling:
            sleep(self.poll_frequency)

    def resync_uids_impl(self):
        # NOTE: first, let's check if the UIVDALIDITY change was spurious, if
        # it is, just discard it and go on, if it isn't, drop the relevant
        # entries (filtering by account and folder IDs) from the imapuid table,
        # download messages, if necessary - in case a message has changed UID -
        # update UIDs, and discard orphaned messages. -siro
        with session_scope() as db_session:
            account = db_session.query(Account).get(self.account_id)
            folder_info = db_session.query(ImapFolderInfo). \
                filter_by(account_id=self.account_id,
                          folder_id=self.folder_id).one()
            cached_uidvalidity = folder_info.uidvalidity
            with self.conn_pool.get() as crispin_client:
                crispin_client.select_folder(self.folder_name,
                                             lambda *args: True)
                uidvalidity = crispin_client.selected_uidvalidity
                uidnext = crispin_client.selected_uidnext
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
            for message in data_sha256_message.itervalues():
                db_session.delete(message)
            folder_info.uidvalidity = uidvalidity
            folder_info.highestmodseq = None
            folder_info.uidnext = uidnext

    @retry_crispin
    def poll_for_changes(self):
        log.new(account_id=self.account_id, folder=self.folder_name)
        while True:
            log.info('polling for changes')
            self.poll_impl()

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

        new_uid = common.create_imap_message(db_session, acct, folder, msg)
        self.add_message_to_thread(db_session, new_uid.message, msg)

        db_session.flush()

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

    def add_message_to_thread(self, db_session, message_obj, raw_message):
        """Associate message_obj to the right Thread object, creating a new
        thread if necessary."""
        with db_session.no_autoflush:
            # Disable autoflush so we don't try to flush a message with null
            # thread_id.
            parent_thread = fetch_corresponding_thread(
                db_session, self.namespace_id, message_obj)
            construct_new_thread = True

            if parent_thread:
                # If there's a parent thread that isn't too long already,
                # add to it. Otherwise create a new thread.
                parent_message_count = self._count_thread_messages(
                    parent_thread.id, db_session)
                if parent_message_count < MAX_THREAD_LENGTH:
                    construct_new_thread = False

            if construct_new_thread:
                message_obj.thread = ImapThread.from_imap_message(
                    db_session, self.namespace_id, message_obj)
            else:
                parent_thread.messages.append(message_obj)

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
            with session_scope() as db_session:
                account = Account.get(self.account_id, db_session)
                folder = Folder.get(self.folder_id, db_session)
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

        with session_scope() as db_session:
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

    def get_new_uids(self, crispin_client):
        remote_uidnext = crispin_client.conn.folder_status(
            self.folder_name, ['UIDNEXT'])['UIDNEXT']
        if remote_uidnext is not None and remote_uidnext == self.uidnext:
            return

        crispin_client.select_folder(self.folder_name, self.uidvalidity_cb)
        # Some servers don't return a UIDNEXT, so we have to actually get the
        # last UID.
        if remote_uidnext is None:
            max_uid = crispin_client.conn.fetch('*', ['UID'])
            if not max_uid:
                # No UIDs in folder
                return
            remote_uidnext = max(max_uid.keys()) + 1
        with session_scope() as db_session:
            lastseenuid = common.lastseenuid(self.account_id, db_session,
                                             self.folder_id)
        new_uids = range(lastseenuid + 1, remote_uidnext)
        for uid in new_uids:
            self.download_and_commit_uids(crispin_client, [uid])
        self.uidnext = remote_uidnext

    def condstore_refresh_flags(self, crispin_client):
        new_highestmodseq = crispin_client.conn.folder_status(
            self.folder_name, ['HIGHESTMODSEQ'])['HIGHESTMODSEQ']
        # Ensure that we have an initial highestmodseq value stored before we
        # begin polling for changes.
        if self.highestmodseq is None:
            self.highestmodseq = new_highestmodseq

        if new_highestmodseq == self.highestmodseq:
            # Don't need to do anything if the highestmodseq hasn't
            # changed.
            return
        elif new_highestmodseq < self.highestmodseq:
            # This should really never happen, but if it does, handle it.
            log.warning('got server highestmodseq less than saved '
                        'highestmodseq',
                        new_highestmodseq=new_highestmodseq,
                        saved_highestmodseq=self.highestmodseq)
            return

        # Highestmodseq has changed, update accordingly.
        crispin_client.select_folder(self.folder_name, self.uidvalidity_cb)
        changed_flags = crispin_client.condstore_changed_flags(
            self.highestmodseq)
        remote_uids = crispin_client.all_uids()
        with session_scope() as db_session:
            common.update_metadata(self.account_id, self.folder_id,
                                   changed_flags, db_session)
            local_uids = common.local_uids(self.account_id, db_session,
                                           self.folder_id)
            expunged_uids = set(local_uids).difference(remote_uids)
            common.remove_deleted_uids(self.account_id, self.folder_id,
                                       expunged_uids, db_session)
            db_session.commit()

    def generic_refresh_flags(self, crispin_client):
        now = datetime.utcnow()
        slow_refresh_due = (
            self.last_slow_refresh is None or
            now > self.last_slow_refresh + SLOW_REFRESH_INTERVAL
        )
        fast_refresh_due = (
            self.last_fast_refresh is None or
            now > self.last_fast_refresh + FAST_REFRESH_INTERVAL
        )
        if slow_refresh_due:
            self.refresh_flags_impl(crispin_client, SLOW_FLAGS_REFRESH_LIMIT)
            self.last_slow_refresh = datetime.utcnow()
        elif fast_refresh_due:
            self.refresh_flags_impl(crispin_client, FAST_FLAGS_REFRESH_LIMIT)
            self.last_fast_refresh = datetime.utcnow()

    def refresh_flags_impl(self, crispin_client, max_uids):
        crispin_client.select_folder(self.folder_name, self.uidvalidity_cb)
        with session_scope() as db_session:
            local_uids = common.local_uids(account_id=self.account_id,
                                           session=db_session,
                                           folder_id=self.folder_id,
                                           limit=max_uids)

        flags = crispin_client.flags(local_uids)
        expunged_uids = set(local_uids).difference(flags.keys())
        with session_scope() as db_session:
            common.remove_deleted_uids(self.account_id, self.folder_id,
                                       expunged_uids, db_session)
            common.update_metadata(self.account_id, self.folder_id,
                                   flags, db_session)

    def check_uid_changes(self, crispin_client):
        self.get_new_uids(crispin_client)
        if crispin_client.condstore_supported():
            self.condstore_refresh_flags(crispin_client)
        else:
            self.generic_refresh_flags(crispin_client)

    @property
    def uidvalidity(self):
        if not hasattr(self, '_uidvalidity'):
            self._uidvalidity = self._load_imap_folder_info().uidvalidity
        return self._uidvalidity

    @property
    def uidnext(self):
        if not hasattr(self, '_uidnext'):
            self._uidnext = self._load_imap_folder_info().uidnext
        return self._uidnext

    @uidnext.setter
    def uidnext(self, value):
        self._update_imap_folder_info('uidnext', value)
        self._uidnext = value

    @property
    def last_slow_refresh(self):
        # We persist the last_slow_refresh timestamp so that we don't end up
        # doing a (potentially expensive) full flags refresh for every account
        # on every process restart.
        if not hasattr(self, '_last_slow_refresh'):
            self._last_slow_refresh = self._load_imap_folder_info(). \
                last_slow_refresh
        return self._last_slow_refresh

    @last_slow_refresh.setter
    def last_slow_refresh(self, value):
        self._update_imap_folder_info('last_slow_refresh', value)
        self._last_slow_refresh = value

    @property
    def highestmodseq(self):
        if not hasattr(self, '_highestmodseq'):
            self._highestmodseq = self._load_imap_folder_info().highestmodseq
        return self._highestmodseq

    @highestmodseq.setter
    def highestmodseq(self, value):
        self._highestmodseq = value
        self._update_imap_folder_info('highestmodseq', value)

    def _load_imap_folder_info(self):
        with session_scope() as db_session:
            imapfolderinfo = db_session.query(ImapFolderInfo). \
                filter(ImapFolderInfo.account_id == self.account_id,
                       ImapFolderInfo.folder_id == self.folder_id). \
                one()
            db_session.expunge(imapfolderinfo)
            return imapfolderinfo

    def _update_imap_folder_info(self, attrname, value):
        with session_scope() as db_session:
            imapfolderinfo = db_session.query(ImapFolderInfo). \
                filter(ImapFolderInfo.account_id == self.account_id,
                       ImapFolderInfo.folder_id == self.folder_id). \
                one()
            setattr(imapfolderinfo, attrname, value)
            db_session.commit()

    def uidvalidity_cb(self, account_id, folder_name, select_info):
        assert folder_name == self.folder_name
        assert account_id == self.account_id
        selected_uidvalidity = select_info['UIDVALIDITY']
        is_valid = (self.uidvalidity is None or
                    selected_uidvalidity <= self.uidvalidity)
        if not is_valid:
            raise UidInvalid(
                'folder: {}, remote uidvalidity: {}, '
                'cached uidvalidity: {}'.format(folder_name.encode('utf-8'),
                                                selected_uidvalidity,
                                                self.uidvalidity))
        return select_info


# This version is elsewhere in the codebase, so keep it for now
# TODO(emfree): clean this up.
def uidvalidity_cb(account_id, folder_name, select_info):
    assert folder_name is not None and select_info is not None, \
        "must start IMAP session before verifying UIDVALIDITY"
    with session_scope() as db_session:
        saved_folder_info = common.get_folder_info(account_id, db_session,
                                                   folder_name)
        saved_uidvalidity = or_none(saved_folder_info, lambda i:
                                    i.uidvalidity)
    selected_uidvalidity = select_info['UIDVALIDITY']
    if saved_folder_info:
        is_valid = (saved_uidvalidity is None or
                    selected_uidvalidity <= saved_uidvalidity)
        if not is_valid:
            raise UidInvalid(
                'folder: {}, remote uidvalidity: {}, '
                'cached uidvalidity: {}'.format(folder_name.encode('utf-8'),
                                                selected_uidvalidity,
                                                saved_uidvalidity))
    return select_info
