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
import imaplib
from sqlalchemy import func
from sqlalchemy.orm import load_only
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound

from inbox.basicauth import ValidationError
from inbox.util.concurrency import retry_with_logging
from inbox.util.debug import bind_context
from inbox.util.itert import chunk
from inbox.util.misc import or_none
from inbox.mailsync.backends.imap import metrics
from inbox.util.threading import fetch_corresponding_thread, MAX_THREAD_LENGTH, add_message_to_thread
from inbox.util.stats import statsd_client
from nylas.logging import get_logger
log = get_logger()
from inbox.crispin import connection_pool, retry_crispin, FolderMissingError
from inbox.models import Folder, Account, Message
from inbox.models.backends.imap import (ImapFolderSyncStatus, ImapThread,
                                        ImapUid, ImapFolderInfo)
from inbox.models.session import session_scope
from inbox.mailsync.backends.imap import common
from inbox.mailsync.backends.base import (MailsyncDone, MailsyncError,
                                          THROTTLE_COUNT, THROTTLE_WAIT)
from inbox.heartbeat.store import HeartbeatStatusProxy
from inbox.events.ical import import_attached_events


# Idle doesn't necessarily pick up flag changes, so we don't want to
# idle for very long, or we won't detect things like messages being
# marked as read.
IDLE_WAIT = 30
DEFAULT_POLL_FREQUENCY = 30
INBOX_POLL_FREQUENCY = 10  # Poll on the Inbox folder more often.

FAST_FLAGS_REFRESH_LIMIT = 100
SLOW_FLAGS_REFRESH_LIMIT = 2000
SLOW_REFRESH_INTERVAL = timedelta(seconds=3600)
FAST_REFRESH_INTERVAL = timedelta(seconds=30)

# Maximum number of uidinvalidity errors in a row.
MAX_UIDINVALID_RESYNCS = 5

CONDSTORE_FLAGS_REFRESH_BATCH_SIZE = 200


class FolderSyncEngine(Greenlet):
    """Base class for a per-folder IMAP sync engine."""

    def __init__(self, account_id, namespace_id, folder_name,
                 email_address, provider_name, syncmanager_lock):

        with session_scope(namespace_id) as db_session:
            try:
                folder = db_session.query(Folder). \
                    filter(Folder.name == folder_name,
                           Folder.account_id == account_id).one()
            except NoResultFound:
                raise MailsyncError(u"Missing Folder '{}' on account {}"
                                    .format(folder_name, account_id))

            self.folder_id = folder.id
            self.folder_role = folder.canonical_name

        bind_context(self, 'foldersyncengine', account_id, self.folder_id)
        self.account_id = account_id
        self.namespace_id = namespace_id
        self.folder_name = folder_name
        self.email_address = email_address
        self.syncmanager_lock = syncmanager_lock
        self.provider_name = provider_name
        self.flags_fetch_results = {}
        self.conn_pool = connection_pool(self.account_id)

        # Extend logging context to always include our info
        self.log = log.new(account_id=self.account_id, folder=self.folder_name,
                           folder_id=self.folder_id, provider=self.provider_name)

        self.heartbeat_status = HeartbeatStatusProxy(self.account_id,
                                                     self.folder_id,
                                                     self.folder_name,
                                                     self.email_address,
                                                     self.provider_name)
        Greenlet.__init__(self)

        # Some generic IMAP servers are throwing UIDVALIDITY
        # errors forever. Instead of resyncing those servers
        # ad vitam, we keep track of the number of consecutive
        # times we got such an error and bail out if it's higher than
        # MAX_UIDINVALID_RESYNCS.
        self.uidinvalid_count = 0

    def _run(self):
        try:
            self._initialize_imap_state()
        except IntegrityError:
            # The state insert failed because the folder ID ForeignKey
            # was no longer valid, ie. the folder for this engine was deleted
            # while we were starting up.
            # Exit the sync and let the monitor sort things out.
            self.log.info("Folder state loading failed due to IntegrityError")
            raise MailsyncDone()

        return retry_with_logging(self._run_impl, account_id=self.account_id,
                                  provider=self.provider_name, logger=log)

    def _run_impl(self):
        # NOTE: The parent ImapSyncMonitor handler could kill us at any
        # time if it receives a shutdown command. The shutdown command is
        # equivalent to ctrl-c.
        while True:
            try:
                self._sync_impl()
                # We've been through a normal cycle without raising any
                # error. It's safe to reset the uidvalidity counter.
                self.uidinvalid_count = 0
            except UidInvalid:
                self.encountered_uidinvalidity()

            except FolderMissingError:
                # Folder was deleted by monitor while its sync was running.
                # TODO: Monitor should handle shutting down the folder engine.
                self.log.info('Folder disappeared. Stopping sync.')
                raise MailsyncDone()

            except ValidationError as exc:
                self.log.error('Error authenticating; stopping sync',
                                exc_info=True, logstash_tag='mark_invalid')
                with session_scope(self.namespace_id) as db_session:
                    account = db_session.query(Account).get(self.account_id)
                    account.mark_invalid()
                    account.update_sync_error(str(exc))
                raise MailsyncDone()

            finally:
                self._update_imap_state()

    def _load_imap_folder_info(self):
        with session_scope(self.namespace_id) as db_session:
            return imapfolderinfo

    def _initialize_imap_state(self):
        with session_scope(self.namespace_id) as db_session:
            self.folder_info = db_session.query(ImapFolderInfo). \
                filter(ImapFolderInfo.account_id == self.account_id,
                       ImapFolderInfo.folder_id == self.folder_id). \
                one()
            db_session.expunge(self.folder_info)

    def _update_imap_state(self):
        self.heartbeat_status.publish(state='deprecated')
        self.log.bind(state='deprecated')
        self.folder_info.state = 'deprecated'

        # Don't need to re-query, will auto refresh on re-associate.
        with session_scope(self.namespace_id) as db_session:
            db_session.add(self.folder_info)
            db_session.commit()

    def set_stopped(self, db_session):
        self.folder_info.stop_sync()

    @retry_crispin
    def _sync_impl(self):
        with self.conn_pool.get() as crispin_client:
            if crispin_client.selected_folder_name != self.folder_name:
                crispin_client.select_folder(self.folder_name, self.uidvalidity_cb)
            highestmodseq = self.get_remote_highestmodseq(crispin_client)
            uidnext = self.get_remote_uidnext(crispin_client)

            # Initialize highestmodseq, to ensure we don't miss changes that occur
            # between first message sync and first flag scan
            if self.folder_info.highestmodseq is None:
                self.folder_info.highestmodseq = highestmodseq

            # Old initial sync:
            # - fetch entire list of UIDs
            # - download them one by one, newest to oldest
            # - separate worker does polling for imap

            # New initial sync:
            #
            # - Identify ranges we want
            # - Fetch ranges
            #   + no ranges? Idle.
            # - Exit
            first_sync = self.folder_info.fetchedmax is None
            ranges = []

            if first_sync:
                ranges.append((uidnext - 500, uidnext))
            else:
                if self.folder_info.fetchedmax < uidnext:
                    ranges.append((self.folder_info.fetchedmax, uidnext))
                if self.folder_info.fetchedmin > 1:
                    ranges.append((self.folder_info.fetchedmin - 500, self.folder_info.fetchedmin))

            if len(ranges) > 0:
                self._sync_ranges(crispin_client, ranges)

            if crispin_client.condstore_supported():
                self._sync_flags_condstore(crispin_client)
            else:
                self._sync_flags_generic(crispin_client)

            if len(ranges) == 0:
                self._sync_idle(crispin_client)

            return

    def _sync_ranges(self, crispin_client, ranges):
        for (start, end) in ranges:
            uids = sorted(range(start, end), reverse=True)
            count = 0
            for uid in uids:
                # The speedup from batching appears to be less clear for
                # non-Gmail accounts, so for now just download one-at-a-time.
                self.download_and_commit_uids(crispin_client, [uid])
                count += 1

    def _sync_idle(self, crispin_client):
        if not crispin_client.idle_supported() or self.folder_role != 'inbox':
            if self.folder_name.lower() == 'inbox':
                sleep(INBOX_POLL_FREQUENCY)
            else:
                sleep(DEFAULT_POLL_FREQUENCY)
            return

        try:
            crispin_client.idle(IDLE_WAIT)
        except Exception as exc:
            # With some servers we get e.g.
            # 'Unexpected IDLE response: * FLAGS  (...)'
            if isinstance(exc, imaplib.IMAP4.error) and \
                    exc.message.startswith('Unexpected IDLE response'):
                self.log.info('Error initiating IDLE, not idling',
                              error=exc)
                try:
                    # Still have to take the connection out of IDLE
                    # mode to reuse it though.
                    crispin_client.conn.idle_done()
                except AttributeError:
                    pass
                idling = False
            else:
                raise

    def encountered_uidinvalidity(self):
        with self.conn_pool.get() as crispin_client:
            crispin_client.select_folder(self.folder_name, self.uidvalidity_cb)
            self.uidinvalid_count += 1

            if self.uidinvalid_count < MAX_UIDINVALID_RESYNCS:
                self._recover_from_uidinvalidity_impl(crispin_client)
            else:
                # Check that we're not stuck in an endless uidinvalidity resync loop.
                self.log.error('Resynced more than MAX_UIDINVALID_RESYNCS in a'
                               ' row. Stopping sync.')

                with session_scope(self.namespace_id) as db_session:
                    account = db_session.query(Account).get(self.account_id)
                    account.disable_sync('Detected endless uidvalidity resync loop')
                    account.sync_state = 'stopped'
                    db_session.commit()

                raise MailsyncDone()

    def _recover_from_uidinvalidity_impl(self, crispin_client):
        # First, let's check if the UIVDALIDITY change was spurious, if
        # it is, just discard it and go on.
        remote_uidvalidity = crispin_client.selected_uidvalidity
        remote_uidnext = crispin_client.selected_uidnext
        if remote_uidvalidity <= self.folder_info.uidvalidity:
            self.log.debug('UIDVALIDITY unchanged')
            return

        # Otherwise, if the UIDVALIDITY really has changed, discard all saved
        # UIDs for the folder, mark associated messages for garbage-collection,
        # and return to the 'initial' state to resync.
        # This will cause message and threads to be deleted and recreated, but
        # uidinvalidity is sufficiently rare that this tradeoff is acceptable.
        with session_scope(self.namespace_id) as db_session:
            invalid_uids = {
                uid for uid, in db_session.query(ImapUid.msg_uid).
                filter_by(account_id=self.account_id,
                          folder_id=self.folder_id)
            }
        common.remove_deleted_uids(self.account_id, self.folder_id, invalid_uids)

        self.folder_info.highestmodseq = self.get_remote_highestmodseq(crispin_client)
        self.folder_info.uidvalidity = remote_uidvalidity
        self.folder_info.uidnext = remote_uidnext

    def create_message(self, db_session, acct, folder, msg):
        assert acct is not None and acct.namespace is not None

        # Check if we somehow already saved the imapuid (shouldn't happen, but
        # possible due to race condition). If so, don't commit changes.
        existing_imapuid = db_session.query(ImapUid).filter(
            ImapUid.account_id == acct.id, ImapUid.folder_id == folder.id,
            ImapUid.msg_uid == msg.uid).first()
        if existing_imapuid is not None:
            self.log.error('Expected to create imapuid, but existing row found',
                           remote_msg_uid=msg.uid,
                           existing_imapuid=existing_imapuid.id)
            return None

        new_uid = common.create_imap_message(db_session, acct, folder, msg)
        add_message_to_thread(db_session, new_uid.message, msg)

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
            metrics.report_message_creation_latency(new_uid.message)

        return new_uid

    def download_and_commit_uids(self, crispin_client, uids):
        start = datetime.utcnow()
        raw_messages = crispin_client.uids(uids)
        if not raw_messages:
            return 0

        new_uids = set()
        with self.syncmanager_lock:
            with session_scope(self.namespace_id) as db_session:
                account = Account.get(self.account_id, db_session)
                folder = Folder.get(self.folder_id, db_session)
                for msg in raw_messages:
                    uid = self.create_message(db_session, account,
                                              folder, msg)
                    if uid is not None:
                        db_session.add(uid)
                        db_session.flush()
                        new_uids.add(uid)
                db_session.commit()

        self.log.info('Committed new UIDs',
                      new_committed_message_count=len(new_uids))
        # If we downloaded uids, record message velocity (#uid / latency)
        if len(new_uids):
            metrics.report_message_velocity(datetime.utcnow() - start,
                                          len(new_uids))
        return len(new_uids)

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

    def get_remote_uidnext(self, crispin_client):
        try:
            return crispin_client.conn.folder_status(
                self.folder_name, ['UIDNEXT']).get('UIDNEXT')
        except imaplib.IMAP4.error as e:
            if '[NONEXISTENT]' in e.message:
                raise FolderMissingError()
            else:
                raise e

    def get_remote_highestmodseq(self, crispin_client):
        return crispin_client.conn.folder_status(
            self.folder_name, ['HIGHESTMODSEQ'])['HIGHESTMODSEQ']
        # TODO Ben: Why is there no error handling for this?

    def _sync_flags_condstore(self, crispin_client):
        highestmodseq = self.folder_info.highestmodseq
        assert(highestmodseq is not None)

        new_highestmodseq = self.get_remote_highestmodseq()

        if new_highestmodseq == highestmodseq:
            # Don't need to do anything if the highestmodseq hasn't
            # changed.
            return

        if new_highestmodseq < highestmodseq:
            # This should really never happen, but if it does, handle it.
            self.log.warning('got server highestmodseq less than saved '
                             'highestmodseq',
                             new_highestmodseq=new_highestmodseq,
                             cached_highestmodseq=highestmodseq)
            return

        self.log.info('HIGHESTMODSEQ has changed, getting changed UIDs',
                      new_highestmodseq=new_highestmodseq,
                      saved_highestmodseq=highestmodseq)

        changed_flags = crispin_client.condstore_changed_flags(highestmodseq)
        remote_uids = crispin_client.all_uids()

        # Cap at 100 flag changes. Since this code runs as part of a larger
        # sync loop, we'll get all of them as long as we go oldest => newest.
        flag_batches = chunk(
            sorted(changed_flags.items(), key=lambda (k, v): v.modseq),
            CONDSTORE_FLAGS_REFRESH_BATCH_SIZE)
        for flag_batch in flag_batches:
            with session_scope(self.namespace_id) as db_session:
                common.update_metadata(self.account_id, self.folder_id,
                                       self.folder_role, dict(flag_batch),
                                       db_session)
            if len(flag_batch) == CONDSTORE_FLAGS_REFRESH_BATCH_SIZE:
                interim_highestmodseq = max(v.modseq for k, v in flag_batch)
                self.folder_info.highestmodseq = interim_highestmodseq

        with session_scope(self.namespace_id) as db_session:
            local_uids = common.local_uids(self.account_id, db_session, self.folder_id)
            expunged_uids = set(local_uids).difference(remote_uids)

        if expunged_uids:
            common.remove_deleted_uids(self.account_id, self.folder_id, expunged_uids)
        self.folder_info.highestmodseq = new_highestmodseq

    def _sync_flags_generic(self, crispin_client):
        now = datetime.utcnow()
        slow_refresh_due = (
            self.folder_info.last_slow_refresh is None or
            now > self.folder_info.last_slow_refresh + SLOW_REFRESH_INTERVAL
        )
        fast_refresh_due = (
            self.folder_info.last_fast_refresh is None or
            now > self.folder_info.last_fast_refresh + FAST_REFRESH_INTERVAL
        )
        if slow_refresh_due:
            self._sync_flags_to_depth(crispin_client, SLOW_FLAGS_REFRESH_LIMIT)
            self.folder_info.last_fast_refresh = datetime.utcnow()
            self.folder_info.last_slow_refresh = datetime.utcnow()
        elif fast_refresh_due:
            self._sync_flags_to_depth(crispin_client, FAST_FLAGS_REFRESH_LIMIT)
            self.folder_info.last_fast_refresh = datetime.utcnow()

    def _sync_flags_to_depth(self, crispin_client, max_uids):
        with session_scope(self.namespace_id) as db_session:
            local_uids = common.local_uids(account_id=self.account_id,
                                           session=db_session,
                                           folder_id=self.folder_id,
                                           limit=max_uids)

        flags = crispin_client.flags(local_uids)
        if (max_uids in self.flags_fetch_results and
                self.flags_fetch_results[max_uids] == (local_uids, flags)):
            # If the flags fetch response is exactly the same as the last one
            # we got, then we don't need to persist any changes.
            self.log.debug('Unchanged flags refresh response, '
                           'not persisting changes', max_uids=max_uids)
            return
        self.log.debug('Changed flags refresh response, persisting changes',
                       max_uids=max_uids)
        expunged_uids = set(local_uids).difference(flags.keys())
        common.remove_deleted_uids(self.account_id, self.folder_id,
                                   expunged_uids)
        with session_scope(self.namespace_id) as db_session:
            common.update_metadata(self.account_id, self.folder_id,
                                   self.folder_role, flags, db_session)
        self.flags_fetch_results[max_uids] = (local_uids, flags)

    def uidvalidity_cb(self, account_id, folder_name, select_info):
        assert folder_name == self.folder_name
        assert account_id == self.account_id

        uidvalidity = self.folder_info.uidvalidity
        selected_uidvalidity = select_info['UIDVALIDITY']

        is_valid = (uidvalidity is None or selected_uidvalidity <= uidvalidity)
        if not is_valid:
            raise UidInvalid(
                'folder: {}, remote uidvalidity: {}, '
                'cached uidvalidity: {}'.format(folder_name.encode('utf-8'),
                                                selected_uidvalidity,
                                                uidvalidity))
        return select_info


class UidInvalid(Exception):
    """Raised when a folder's UIDVALIDITY changes, requiring a resync."""
    pass
