from __future__ import division
import socket

from .sessionmanager import get_crispin_from_email
from .models import db_session, FolderMeta, MessageMeta, UIDValidity, IMAPAccount
from sqlalchemy import distinct
import sqlalchemy.exc

from .encoding import EncodingError
from ..util.itert import chunk, partition
from ..util.cache import set_cache, get_cache, rm_cache

from .log import configure_sync_logging, get_logger
log = get_logger()

from gc import collect as garbge_collect
from datetime import datetime

from gevent import Greenlet, sleep, joinall, kill
from gevent.queue import Queue, Empty

from .google_oauth import InvalidOauthGrantException

def refresh_crispin(email, dummy=False):
    try:
        return get_crispin_from_email(email, dummy)
    except InvalidOauthGrantException, e:
        log.error("Error refreshing crispin on {0} because {1}".format(email, e))
        raise e

def load_validity_cache(crispin_client):
    # in practice UIDVALIDITY and HIGHESTMODSEQ are always positive
    # integers with gmail, but let's not take chances on our default.
    defaults = dict(UIDVALIDITY=float('-inf'), HIGHESTMODSEQ=float('-inf'))
    # populated cache looks like:
    # {'Inbox': {'UIDVALIDITY': 123, 'HIGHESTMODSEQ': 456}}
    cache_validity = dict([(folder, defaults.copy())
        for folder in crispin_client.sync_folders])
    for folder, uid_validity, highestmodseq in db_session.query(
            UIDValidity.folder_name,
            UIDValidity.uid_validity,
            UIDValidity.highestmodseq).filter_by(
                    account_id=crispin_client.account.id):
        cache_validity[folder] = dict(UIDVALIDITY=uid_validity,
                HIGHESTMODSEQ=highestmodseq)

    return cache_validity

def check_uidvalidity(crispin_client, cached_validity=None):
    valid = uidvalidity_valid(crispin_client, cached_validity)
    if not valid:
        log.info("UIDVALIDITY for {0} has changed; resyncing UIDs".format(
            crispin_client.selected_folder_name))
        resync_uids(crispin_client)
    return valid

def fetch_uidvalidity(account, folder_name):
    try:
        # using .one() here may catch duplication bugs
        return db_session.query(UIDValidity).filter_by(
                account=account, folder_name=folder_name).one()
    except sqlalchemy.orm.exc.NoResultFound:
        return None

def uidvalidity_valid(crispin_client, cached_validity=False):
    """ Validate UIDVALIDITY on currently selected folder. """
    if cached_validity is None:
        cached_validity = fetch_uidvalidity(crispin_client.account,
                crispin_client.selected_folder_name).uid_validity
        assert type(cached_validity) == type(crispin_client.selected_uidvalidity), "cached_validity: {0} / selected_uidvalidity: {1}".format(type(cached_validity), type(crispin_client.selected_uidvalidity))

    if cached_validity is None:
        return True
    else:
        return crispin_client.selected_uidvalidity >= cached_validity

def resync_uids(crispin_client):
    """ Call this when UIDVALIDITY is invalid to fix up the database.

    What happens here is we fetch new UIDs from the IMAP server and match
    them with X-GM-MSGIDs and sub in the new UIDs for the old. No messages
    are re-downloaded.
    """
    raise Exception("Unimplemented")

def delete_messages(uids, folder, account_id):
    # delete these UIDs from this folder
    fm_query = db_session.query(FolderMeta).filter(
            FolderMeta.msg_uid.in_(uids),
            FolderMeta.folder_name==folder,
            FolderMeta.imapaccount_id==account_id)
    # g_msgids = [fm.g_msgid for fm in fm_query]
    fm_query.delete(synchronize_session='fetch')

    # XXX TODO not sure if there's a good non-expensive way to find
    # dangling messages; we may want to have a different worker deal
    # with this
    # if the g_msgid is now dangling, delete the message meta and parts as
    # well
    # dangling_g_msgids = [g_msgid for g_msgid, count in
    # db_session.query(FolderMeta.g_msgid,
    #     func.count(FolderMeta)).group_by(FolderMeta.g_msgid)\
    #         .filter(FolderMeta.g_msgid.in_(g_msgids)) if count == 0]
    # #
    # db_session.query(MessageMeta).filter(
    #         MessageMeta.g_msgids.in_(dangling_g_msgids)).delete()
    # db_session.query(BlockMeta).filter(
    #         BlockMeta.g_msgids.in_(dangling_g_msgids)).delete()
    # XXX also delete message parts from the block store
    db_session.commit()

def new_or_updated(uids, folder, account_id, local_uids=None):
    if local_uids is None:
        local_uids = set([unicode(uid) for uid, in \
                db_session.query(FolderMeta.msg_uid).filter(
                FolderMeta.folder_name==folder,
                FolderMeta.imapaccount_id==account_id,
                FolderMeta.msg_uid.in_(uids))])
    return partition(lambda x: x not in local_uids, uids)

def g_check_join(threads, errmsg):
    """ Block until all threads have completed and throw an error if threads
        are not successful.
    """
    joinall(threads)
    errors = [thread.exception for thread in threads if not thread.successful()]
    if errors:
        log.error(errmsg)
        for error in errors:
            log.error(error)
        raise SyncException("Fatal error encountered")

def safe_download(uids, folder, crispin_client):
    try:
        new_messages, new_foldermeta = crispin_client.fetch_uids(uids)
    except EncodingError, e:
        log.error(e)
        raise e
    except MemoryError, e:
        log.error("Ran out of memory while fetching UIDs %s" % uids)
        raise e
    # XXX make this catch more specific
    # except Exception, e:
    #     log.error("Crispin fetch failure: %s. Reconnecting..." % e)
    #     crispin_client = refresh_crispin(crispin_client.email_address)
    #     new_messages, new_foldermeta = crispin_client.fetch_uids(uids)

    return new_messages, new_foldermeta

class SyncException(Exception): pass

class SyncMonitor(Greenlet):
    def __init__(self, account, status_callback, n=5):
        self.account = account
        self.n = n
        self.status_callback = status_callback
        self.inbox = Queue()
        self.log = configure_sync_logging(account)
        self.crispin_client = refresh_crispin(account.email_address)
        Greenlet.__init__(self)

    def _run(self):
        action = Greenlet.spawn(self.action)
        while not action.ready():
            try:
                cmd = self.inbox.get_nowait()
                if not self.process_command(cmd):
                    self.log.info("Stopping sync for {0}".format(
                        self.account.email_address))
                    kill(action)
                    return
            except Empty: sleep(1)

    def process_command(self, cmd):
        """ Returns True if successful, or False if process should abort. """
        self.log.info("processing command {0}".format(cmd))
        return cmd != 'shutdown'

    def action(self):
        while not self.account.initial_sync_done:
            self.initial_sync()

        self.status_callback(self.account, 'poll', None)

        polling = True  # FOREVER
        while polling:
            self.poll()
            sleep(0)

    def _remove_deleted_messages(self):
        """ Works as follows:
            1. do a LIST on the current folder to see what messages are on the server
            2. compare to message uids stored locally
            3. purge messages we have locally but not on the server. ignore
                messages we have on the server that aren't local.
        """
        server_uids = self.crispin_client.all_uids()
        local_uids = [uid for uid, in
                db_session.query(FolderMeta.msg_uid).filter_by(
                    folder_name=self.crispin_client.selected_folder_name,
                    imapaccount_id=self.crispin_client.account.id)]
        if len(server_uids) > 0 and len(local_uids) > 0:
            assert type(server_uids[0]) != type('')

        to_delete = set(local_uids).difference(set(server_uids))
        if to_delete:
            delete_messages(to_delete, self.crispin_client.selected_folder_name,
                    self.crispin_client.account.id)
            self.log.info("Deleted {0} removed messages".format(len(to_delete)))

    def _update_metadata(self, uids):
        """ Update flags (the only metadata that can change). """
        new_metadata = self.crispin_client.fetch_metadata(uids)
        self.log.info("new metadata: {0}".format(new_metadata))
        for fm in db_session.query(FolderMeta).filter(
                FolderMeta.msg_uid.in_(uids),
                FolderMeta.imapaccount_id==self.crispin_client.account.id,
                FolderMeta.folder_name==self.crispin_client.selected_folder_name):
            self.log.info("msg: {0}, flags: {1}".format(fm.msg_uid, fm.flags))
            if fm.flags != new_metadata[fm.msg_uid]:
                fm.flags = new_metadata[fm.msg_uid]
                db_session.add(fm)
        # XXX TODO: assert that server uids == local uids?

    def _initial_sync(self, updates, dummy=False):
        """ Downloads entire messages and
        (1) creates the metadata database
        (2) stores message parts to the block store

        Percent-done and completion messages are sent to the 'updates' queue.
        """
        self.log.info('Syncing mail for {0}'.format(self.account.email_address))

        # message download for messages from sync_folders is prioritized before
        # AllMail in the order of appearance in this list

        folder_sync_percent_done = dict([(folder, 0) \
                for folder in self.crispin_client.sync_folders])

        for folder in self.crispin_client.sync_folders:
            # for each folder, compare what's on the server to what we have.
            # this allows restarts of the initial sync script in the case of
            # total failure.
            local_uids = [uid for uid, in
                    db_session.query(FolderMeta.msg_uid).filter_by(
                        imapaccount_id=self.account.id,
                        folder_name=folder)]
            self.crispin_client.select_folder(folder)

            server_g_msgids = None
            cached_validity = fetch_uidvalidity(self.account, folder)
            if cached_validity is not None:
                check_uidvalidity(self.crispin_client, cached_validity.uid_validity)
                self.log.info("Attempting to retrieve server_uids and server_g_msgids from cache")
                server_g_msgids = get_cache("_".join(
                    [self.account.email_address, folder, "server_g_msgids"]))

            if server_g_msgids is not None:
                self.log.info("Successfully retrieved cache")
                # check for updates since last HIGHESTMODSEQ
                cached_highestmodseq = cached_validity.highestmodseq
                if self.crispin_client.selected_highestmodseq > cached_highestmodseq:
                    self.log.info("Updating cache with latest changes")
                    # any uids we don't already have will be downloaded correctly
                    # as usual, but updated uids need to be updated manually
                    modified = self.crispin_client.get_changed_uids(
                            self.crispin_client.selected_highestmodseq)
                    new, updated = new_or_updated(modified, folder,
                            self.account.id, local_uids)
                    self.log.info("{0} new and {1} updated UIDs".format(len(new), len(updated)))
                    # for new, query g_msgids and update cache
                    server_g_msgids.update(self.crispin_client.fetch_g_msgids(new))
                    set_cache("_".join([self.account.email_address, folder,
                        "server_g_msgids"]), server_g_msgids)
                    self.log.info("Updated cache with new messages")
                    # for updated, update them now
                    # bigger chunk because the data being fetched here is very small
                    for uids in chunk(updated, 5*self.crispin_client.CHUNK_SIZE):
                        self._update_metadata(uids)
                        db_session.commit()
                    self.log.info("Updated metadata for modified messages")
            else:
                self.log.info("No cached data found")
                server_g_msgids = self.crispin_client.fetch_g_msgids()
                set_cache("_".join([self.account.email_address, folder,
                    "server_g_msgids"]), server_g_msgids)
                cached_validity = fetch_uidvalidity(self.account, folder)
                if cached_validity is None:
                    db_session.add(UIDValidity(
                        account=self.account,
                        folder_name=folder,
                        uid_validity=self.crispin_client.selected_uidvalidity,
                        highestmodseq=self.crispin_client.selected_highestmodseq))
                    db_session.commit()
                else:
                    cached_validity.uid_validity = self.crispin_client.selected_uidvalidity
                    cached_validity.highestmodseq = self.crispin_client.selected_highestmodseq
                    db_session.add(cached_validity)
                    db_session.commit()
            server_uids = sorted(server_g_msgids.keys())
            # get all g_msgids we've already downloaded for this account
            g_msgids = set([g_msgid for g_msgid, in
                db_session.query(distinct(MessageMeta.g_msgid)).join(FolderMeta).filter(
                    FolderMeta.imapaccount_id==self.account.id)])

            self.log.info("Found {0} UIDs for folder {1}".format(
                len(server_uids), folder))
            self.log.info("Already have {0} items".format(len(local_uids)))
            warn_uids = set(local_uids).difference(set(server_uids))
            unknown_uids = set(server_uids).difference(set(local_uids))

            if warn_uids:
                delete_messages(warn_uids, folder, self.account.id)
                self.log.info("Deleted the following UIDs that no longer exist on the server: {0}".format(' '.join([str(u) for u in sorted(warn_uids)])))

            full_download, foldermeta_only = partition(
                    lambda uid: server_g_msgids[uid] in g_msgids,
                    sorted(unknown_uids))

            self.log.info("{0} uids left to fetch".format(len(full_download)))

            self.log.info("skipping {0} uids downloaded via other folders".format(
                len(foldermeta_only)))
            if len(foldermeta_only) > 0:
                foldermeta_uid_for = dict([(g_msgid, uid) for (uid, g_msgid) \
                        in server_g_msgids.items() if uid in foldermeta_only])
                foldermeta_g_msgids = [server_g_msgids[uid] for uid in foldermeta_only]
                messagemeta_for = dict([(foldermeta_uid_for[mm.g_msgid], mm) for \
                        mm in db_session.query(MessageMeta).filter( \
                            MessageMeta.g_msgid.in_(foldermeta_g_msgids))])
                db_session.add_all(
                        [FolderMeta(imapaccount_id=self.account.id,
                            folder_name=folder, msg_uid=uid, \
                            messagemeta=messagemeta_for[uid]) \
                                    for uid in foldermeta_only])
                db_session.commit()

            total_messages = len(local_uids)

            self.log.info("Starting sync for {0} with chunks of size {1}".format(
                folder, self.crispin_client.CHUNK_SIZE))
            for uids in chunk(reversed(full_download), self.crispin_client.CHUNK_SIZE):
                new_messages, new_foldermeta = safe_download(
                        uids, folder, self.crispin_client)
                db_session.add_all(new_foldermeta)
                db_session.add_all([msg['meta'] for msg in new_messages.values()])
                for msg in new_messages.values():
                    db_session.add_all(msg['parts'])
                    # Save message part blobs before committing changes to db.
                    threads = [Greenlet.spawn(part.save, part._data) \
                            for part in msg['parts']]
                    # Fatally abort if part saves error out. Messages in this
                    # chunk will be retried when the sync is restarted.
                    g_check_join(threads, "Could not save message parts to blob store!")
                    # Clear data stored on BlockMeta objects here. Hopefully this
                    # will help with memory issues.
                    for part in msg['parts']:
                        part._data = None

                garbge_collect()

                db_session.commit()

                total_messages += len(uids)

                percent_done = (total_messages / len(server_uids)) * 100
                folder_sync_percent_done[folder] = percent_done
                updates.put(folder_sync_percent_done)
                self.log.info("Syncing %s -- %.4f%% (%i/%i)" % (
                    self.account.email_address,
                    percent_done,
                    total_messages,
                    len(server_uids)))

            # complete X-GM-MSGID mapping is no longer needed after initial sync
            rm_cache("_".join([self.account.email_address, folder,
                "server_g_msgids"]))
            # XXX TODO: check for consistency with datastore here before
            # committing state: download any missing messages, delete any
            # messages that we have that the server doesn't. that way, worst case
            # if sync engine bugs trickle through is we lose some flags.
            self.log.info("Saved all messages and metadata on {0} to UIDVALIDITY {1} / HIGHESTMODSEQ {2}".format(folder, self.crispin_client.selected_uidvalidity,
                self.crispin_client.selected_highestmodseq))

        self.log.info("Finished.")

    def initial_sync(self):
        updates = Queue()
        process = Greenlet.spawn(self._initial_sync, updates)
        progress = 0
        while not process.ready():
            self.status_callback(self.account, 'initial sync', progress)
            # XXX TODO wrap this in a Timeout in case the process crashes
            progress = updates.get()
            # let monitor accept commands
            sleep(0)
        # process may have finished with some progress left to
        # report; only report the last update
        remaining = [updates.get() for i in xrange(updates.qsize())]
        if remaining:
            self.status_callback(self.account, 'initial sync', remaining[-1])
        if process.successful():
            # we don't do this in initial_sync() to avoid confusion
            # with refreshing the account sqlalchemy object
            self.account.initial_sync_done = True
            db_session.add(self.account)
            db_session.commit()
        else:
            self.log.warning("initial sync for {0} failed: {1}".format(
                self.account.email_address, process.exception))
        assert updates.empty(), "initial sync completed for {0} with {1} progress items left to report: {2}".format(self.account.email_address, updates.qsize(), [updates.get() for i in xrange(updates.qsize())])

    def _highestmodseq_update(self, folder, dummy, highestmodseq=None):
        if highestmodseq is None:
            highestmodseq = db_session.query(UIDValidity).filter_by(
                    account=self.account, folder_name=folder
                    ).one().highestmodseq
        uids = self.crispin_client.get_changed_uids(highestmodseq)
        log.info("Starting highestmodseq update on {0} (current HIGHESTMODSEQ: {1})".format(folder, self.crispin_client.selected_highestmodseq))
        if uids:
            new, updated = new_or_updated(uids, folder,
                    self.crispin_client.account.id)
            log.info("{0} new and {1} updated UIDs".format(len(new), len(updated)))
            for uids in chunk(new, self.crispin_client.CHUNK_SIZE):
                new_messagemeta, new_blockmeta, new_foldermeta = safe_download(new,
                        folder, self.crispin_client)
                db_session.add_all(new_foldermeta)
                db_session.add_all(new_messagemeta)
                db_session.add_all(new_blockmeta)

                # save message data to s3 before committing changes to db
                threads = [Greenlet.spawn(part.save, part._data) \
                        for part in new_blockmeta]
                # Fatally abort if part save fails.
                g_check_join(threads, "Could not save message parts to blob store!")
                # Clear data stored on BlockMeta objects here. Hopefully this will
                # help with memory issues.
                for part in new_blockmeta:
                    part._data = None
                garbge_collect()

                db_session.commit()
            # bigger chunk because the data being fetched here is very small
            for uids in chunk(updated, 5*self.crispin_client.CHUNK_SIZE):
                self._update_metadata(uids)
                db_session.commit()
        else:
            log.info("No changes")

        self._remove_deleted_messages()
        # not sure if this one is actually needed - does delete() automatically
        # commit?
        db_session.commit()

        self._update_cached_highestmodseq(folder)
        db_session.commit()

    def _update_cached_highestmodseq(self, folder, cached_validity=None):
        if cached_validity is None:
            cached_validity = db_session.query(UIDValidity).filter_by(
                    account_id=self.crispin_client.account.id,
                    folder_name=folder).one()
        cached_validity.highestmodseq = self.crispin_client.selected_highestmodseq
        db_session.add(cached_validity)

    def _incremental_sync(self, dummy=False):
        """ Poll this every N seconds for active (logged-in) users and every
            N minutes for logged-out users. It checks for changed message metadata
            and new messages using CONDSTORE / HIGHESTMODSEQ and also checks for
            deleted messages.

            We may also wish to frob update frequencies based on which folder
            a user has visible in the UI as well.
        """
        cache_validity = load_validity_cache(self.crispin_client)
        needs_update = []
        for folder in self.crispin_client.sync_folders:
            # eventually we might want to be holding a cache of this stuff from any
            # SELECT calls that have already happened, to save on a status call.
            # but status is fast, so maybe not.
            status = self.crispin_client.imap_server.folder_status(folder,
                    ('UIDVALIDITY', 'HIGHESTMODSEQ'))
            cached_highestmodseq = cache_validity[folder]['HIGHESTMODSEQ']
            if status['HIGHESTMODSEQ'] > cached_highestmodseq:
                needs_update.append((folder, cached_highestmodseq))

        for folder, highestmodseq in needs_update:
            self.crispin_client.select_folder(folder)
            check_uidvalidity(self.crispin_client)
            self._highestmodseq_update(folder, dummy, highestmodseq)

        return 0

    def poll(self):
        self.log.info("polling {0}".format(self.account.email_address))
        process = Greenlet.spawn(self._incremental_sync, self.account)
        while not process.ready():
            sleep(0)
        if process.successful():
            self.status_callback(self.account, 'poll', datetime.utcnow().isoformat())
        else:
            self.log.warning("incremental update for {0} failed: {1}".format(
                self.account.email_address, process.exception))
        sleep(self.n)

def notify(account, mtype, message):
    """ Pass a message on to the notification dispatcher which deals with
        pubsub stuff.
    """
    # self.log.info("message from {0}: [{1}] {2}".format(
    # account.email_address, mtype, message))

class SyncService:
    """ ZeroRPC interface to syncing. """
    def __init__(self):
        # {'christine.spang@gmail.com': SyncMonitor()}
        self.monitors = dict()
        # READ ONLY from API calls, writes happen from callbacks from monitor
        # greenlets.
        # { 'account_id': { 'state': 'initial sync', 'status': '0'} }
        # 'state' can be ['initial sync', 'poll']
        # 'status' is the percent-done for initial sync, polling start time otherwise
        # all data in here ought to be msgpack-serializable!
        self.statuses = dict()

        # Restart existing active syncs. (Later we will want to partition
        # these across different machines, probably.)
        for email, in db_session.query(IMAPAccount.email_address).filter_by(
                sync_active=True):
            self.start_sync(email)

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
                results[account.email_address] = 'Account {0} is syncing on host {1}'.format(
                        account.email_address, account.sync_host)
            elif account.id not in self.monitors:
                try:
                    account.sync_lock()
                    def update_status(account, state, status):
                        """ I really really wish I were a lambda """
                        self.statuses[account.id] = dict(
                                state=state, status=status)
                        notify(account, state, status)

                    monitor = SyncMonitor(account, update_status)
                    self.monitors[account.id] = monitor
                    monitor.start()
                    account.sync_active = True
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
            return results[email_address]
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
            if not account.sync_active:
                results[account.email_address] = "OK sync stopped already"
            try:
                assert account.sync_host == fqdn, "sync host FQDN doesn't match"
                # XXX Can processing this command fail in some way?
                self.monitors[account.id].inbox.put_nowait("shutdown")
                account.sync_active = False
                account.sync_host = None
                db_session.add(account)
                db_session.commit()
                account.sync_unlock()
                results[account.email_address] = "OK sync stopped"
            except:
                results[account.email_address] = "ERROR error encountered"
        if email_address:
            return results[email_address]
        return results

    def sync_status(self, account_id):
        return self.statuses.get(account_id)

    # XXX this should require some sort of auth or something, used from the
    # admin panel
    def status(self):
        return self.statuses
