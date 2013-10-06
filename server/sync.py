from __future__ import division
import sys, os;  sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..')))
import socket

import sessionmanager
from models import db_session, FolderMeta, MessageMeta, UIDValidity, User
from sqlalchemy import distinct
import sqlalchemy.exc

from encoding import EncodingError
from server.util.itert import chunk, partition
from server.util.cache import set_cache, get_cache, rm_cache
import logging as log
from gc import collect as garbge_collect
from datetime import datetime

from gevent import Greenlet, sleep, joinall, kill
from gevent.queue import Queue, Empty

def refresh_crispin(email, dummy=False):
    return sessionmanager.get_crispin_from_email(email, dummy)

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
            UIDValidity.highestmodseq).filter_by(user=crispin_client.user_obj):
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

def fetch_uidvalidity(user, folder_name):
    try:
        # using .one() here may catch duplication bugs
        return db_session.query(UIDValidity).filter_by(
                user=user, folder_name=folder_name).one()
    except sqlalchemy.orm.exc.NoResultFound:
        return None

def uidvalidity_valid(crispin_client, cached_validity=False):
    """ Validate UIDVALIDITY on currently selected folder. """
    if cached_validity is None:
        cached_validity = fetch_uidvalidity(crispin_client.user_obj,
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

def delete_messages(uids, folder, user_id):
    # delete these UIDs from this folder
    fm_query = db_session.query(FolderMeta).filter(
            FolderMeta.msg_uid.in_(uids),
            FolderMeta.folder_name==folder,
            FolderMeta.user_id==user_id)
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
    # db_session.query(MessagePart).filter(
    #         MessagePart.g_msgids.in_(dangling_g_msgids)).delete()
    # XXX also delete message parts from the block store
    db_session.commit()

def remove_deleted_messages(crispin_client):
    """ Works as follows:
        1. do a LIST on the current folder to see what messages are on the server
        2. compare to message uids stored locally
        3. purge messages we have locally but not on the server. ignore
            messages we have on the server that aren't local.
    """
    server_uids = crispin_client.all_uids()
    local_uids = [uid for uid, in
            db_session.query(FolderMeta.msg_uid).filter_by(
                folder_name=crispin_client.selected_folder_name,
                user_id=crispin_client.user_obj.id)]
    if len(server_uids) > 0 and len(local_uids) > 0:
        assert type(server_uids[0]) != type('')

    to_delete = set(local_uids).difference(set(server_uids))
    if to_delete:
        delete_messages(to_delete, crispin_client.selected_folder_name,
                crispin_client.user_obj.id)
        log.info("Deleted {0} removed messages".format(len(to_delete)))

def new_or_updated(uids, folder, user_id, local_uids=None):
    if local_uids is None:
        local_uids = set([unicode(uid) for uid, in \
                db_session.query(FolderMeta.msg_uid).filter(
                FolderMeta.folder_name==folder,
                FolderMeta.user_id==user_id,
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

def incremental_sync(user, dummy=False):
    """ Poll this every N seconds for active (logged-in) users and every
        N minutes for logged-out users. It checks for changed message metadata
        and new messages using CONDSTORE / HIGHESTMODSEQ and also checks for
        deleted messages.

        We may also wish to frob update frequencies based on which folder
        a user has visible in the UI as well.
    """
    crispin_client = refresh_crispin(user.g_email, dummy)
    cache_validity = load_validity_cache(crispin_client)
    needs_update = []
    for folder in crispin_client.sync_folders:
        # eventually we might want to be holding a cache of this stuff from any
        # SELECT calls that have already happened, to save on a status call.
        # but status is fast, so maybe not.
        status = crispin_client.imap_server.folder_status(folder,
                ('UIDVALIDITY', 'HIGHESTMODSEQ'))
        cached_highestmodseq = cache_validity[folder]['HIGHESTMODSEQ']
        if status['HIGHESTMODSEQ'] > cached_highestmodseq:
            needs_update.append((folder, cached_highestmodseq))

    for folder, highestmodseq in needs_update:
        crispin_client.select_folder(folder)
        check_uidvalidity(crispin_client)
        highestmodseq_update(folder, crispin_client, highestmodseq)

    return 0

def update_cached_highestmodseq(folder, crispin_client, cached_validity=None):
    if cached_validity is None:
        cached_validity = db_session.query(UIDValidity).filter_by(
                user=crispin_client.user_obj, folder_name=folder).one()
    cached_validity.highestmodseq = crispin_client.selected_highestmodseq
    db_session.add(cached_validity)

def highestmodseq_update(folder, crispin_client, highestmodseq=None):
    if highestmodseq is None:
        highestmodseq = db_session.query(UIDValidity).filter_by(
                user=crispin_client.user_obj, folder_name=folder
                ).one().highestmodseq
    uids = crispin_client.get_changed_uids(highestmodseq)
    log.info("Starting highestmodseq update on {0} (current HIGHESTMODSEQ: {1})".format(folder, crispin_client.selected_highestmodseq))
    if uids:
        new, updated = new_or_updated(uids, folder, crispin_client.user_obj.id)
        log.info("{0} new and {1} updated UIDs".format(len(new), len(updated)))
        for uids in chunk(new, crispin_client.CHUNK_SIZE):
            new_messagemeta, new_messagepart, new_foldermeta = safe_download(new,
                    folder, crispin_client)
            db_session.add_all(new_foldermeta)
            db_session.add_all(new_messagemeta)
            db_session.add_all(new_messagepart)

            # save message data to s3 before committing changes to db
            threads = [Greenlet.spawn(part.save, part._data) \
                    for part in new_messagepart]
            # Fatally abort if part save fails.
            g_check_join(threads, "Could not save message parts to blob store!")
            # Clear data stored on MessagePart objects here. Hopefully this will
            # help with memory issues.
            for part in new_messagepart:
                part._data = None
            garbge_collect()

            db_session.commit()
        # bigger chunk because the data being fetched here is very small
        for uids in chunk(updated, 5*crispin_client.CHUNK_SIZE):
            update_metadata(uids, crispin_client)
            db_session.commit()
    else:
        log.info("No changes")

    remove_deleted_messages(crispin_client)
    # not sure if this one is actually needed - does delete() automatically
    # commit?
    db_session.commit()

    update_cached_highestmodseq(folder, crispin_client)
    db_session.commit()

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

def update_metadata(uids, crispin_client):
    """ Update flags (the only metadata that can change). """
    new_metadata = crispin_client.fetch_metadata(uids)
    for fm in db_session.query(FolderMeta).filter(
            FolderMeta.msg_uid.in_(uids),
            FolderMeta.user_id==crispin_client.user_obj.id,
            FolderMeta.folder_name==crispin_client.selected_folder_name):
        log.info("msg: {0}, flags: {1}".format(fm.msg_uid, fm.flags))
        if fm.flags != new_metadata[fm.msg_uid]:
            fm.flags = new_metadata[fm.msg_uid]
            db_session.add(fm)
    # XXX TODO: assert that server uids == local uids?

def get_server_g_msgids(crispin_client):
    pass

def initial_sync(user, updates, dummy=False):
    """ Downloads entire messages and
    (1) creates the metadata database
    (2) stores message parts to the block store

    Percent-done and completion messages are sent to the 'updates' queue.
    """
    crispin_client = refresh_crispin(user.g_email, dummy)

    log.info('Syncing mail for {0}'.format(user.g_email))

    # message download for messages from sync_folders is prioritized before
    # AllMail in the order of appearance in this list

    folder_sync_percent_done = dict([(folder, 0) \
            for folder in crispin_client.sync_folders])

    for folder in crispin_client.sync_folders:
        # for each folder, compare what's on the server to what we have.
        # this allows restarts of the initial sync script in the case of
        # total failure.
        local_uids = [uid for uid, in
                db_session.query(FolderMeta.msg_uid).filter_by(
                    user_id=crispin_client.user_obj.id, folder_name=folder)]
        crispin_client.select_folder(folder)

        server_g_msgids = None
        cached_validity = fetch_uidvalidity(user, folder)
        if cached_validity is not None:
            check_uidvalidity(crispin_client, cached_validity.uid_validity)
            log.info("Attempting to retrieve server_uids and server_g_msgids from cache")
            server_g_msgids = get_cache("_".join([user.g_email, folder,
                "server_g_msgids"]))

        if server_g_msgids is not None:
            log.info("Successfully retrieved cache")
            # check for updates since last HIGHESTMODSEQ
            cached_highestmodseq = cached_validity.highestmodseq
            if crispin_client.selected_highestmodseq > cached_highestmodseq:
                log.info("Updating cache with latest changes")
                # any uids we don't already have will be downloaded correctly
                # as usual, but updated uids need to be updated manually
                modified = crispin_client.get_changed_uids(crispin_client.selected_highestmodseq)
                new, updated = new_or_updated(modified, folder,
                                              crispin_client.user_obj.id,
                                              local_uids)
                log.info("{0} new and {1} updated UIDs".format(len(new), len(updated)))
                # for new, query g_msgids and update cache
                server_g_msgids.update(crispin_client.fetch_g_msgids(new))
                set_cache("_".join([user.g_email, folder,
                    "server_g_msgids"]), server_g_msgids)
                log.info("Updated cache with new messages")
                # for updated, update them now
                # bigger chunk because the data being fetched here is very small
                for uids in chunk(updated, 5*crispin_client.CHUNK_SIZE):
                    update_metadata(uids, crispin_client)
                    db_session.commit()
                log.info("Updated metadata for modified messages")
        else:
            log.info("No cached data found")
            server_g_msgids = crispin_client.fetch_g_msgids()
            set_cache("_".join([user.g_email, folder,
                "server_g_msgids"]), server_g_msgids)
            cached_validity = fetch_uidvalidity(user, folder)
            if cached_validity is None:
                db_session.add(UIDValidity(
                    user=crispin_client.user_obj, folder_name=folder,
                    uid_validity=crispin_client.selected_uidvalidity,
                    highestmodseq=crispin_client.selected_highestmodseq))
                db_session.commit()
            else:
                cached_validity.uid_validity = crispin_client.selected_uidvalidity
                cached_validity.highestmodseq = crispin_client.selected_highestmodseq
                db_session.add(cached_validity)
                db_session.commit()
        server_uids = sorted(server_g_msgids.keys())
        # get all g_msgids we've already downloaded for this user
        g_msgids = set([g_msgid for g_msgid, in
            db_session.query(distinct(MessageMeta.g_msgid)).join(FolderMeta).filter(
                FolderMeta.folder_name==folder,
                FolderMeta.user==crispin_client.user_obj)])

        log.info("Found {0} UIDs for folder {1}".format(
            len(server_uids), folder))
        log.info("Already have {0} items".format(len(local_uids)))
        warn_uids = set(local_uids).difference(set(server_uids))
        unknown_uids = set(server_uids).difference(set(local_uids))

        if warn_uids:
            delete_messages(warn_uids, folder, crispin_client.user_obj.id)
            log.info("Deleted the following UIDs that no longer exist on the server: {0}".format(' '.join([str(u) for u in sorted(warn_uids)])))

        full_download, foldermeta_only = partition(
                lambda uid: server_g_msgids[uid] in g_msgids,
                sorted(unknown_uids))

        log.info("{0} uids left to fetch".format(len(full_download)))

        log.info("skipping {0} uids downloaded via other folders".format(
            len(foldermeta_only)))
        if len(foldermeta_only) > 0:
            foldermeta_uid_for = [server_g_msgids[uid] for uid in foldermeta_only]
            messagemeta_for = dict([(foldermeta_uid_for[mm.g_msgid], mm) for \
                     mm in db_session.query(MessageMeta).filter( \
                         MessageMeta.g_msgid.in_(foldermeta_uid_for.values()))])
            db_session.add_all(
                    [FolderMeta(user=user, folder_name=folder,
                        msg_uid=uid, messagemeta=messagemeta_for[uid]) \
                                for uid in foldermeta_only])
            db_session.commit()

        total_messages = len(local_uids)

        log.info("Starting sync for {0} with chunks of size {1}".format(
            folder, crispin_client.CHUNK_SIZE))
        for uids in chunk(reversed(full_download), crispin_client.CHUNK_SIZE):
            new_messages, new_foldermeta = safe_download(
                    uids, folder, crispin_client)
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
                # Clear data stored on MessagePart objects here. Hopefully this
                # will help with memory issues.
                for part in msg['parts']:
                    part._data = None

            garbge_collect()

            db_session.commit()

            total_messages += len(uids)

            percent_done = (total_messages / len(server_uids)) * 100
            folder_sync_percent_done[folder] = percent_done
            updates.put(folder_sync_percent_done)
            log.info("Synced %i of %i (%.4f%%)" % (total_messages,
                                                   len(server_uids),
                                                   percent_done))

        # complete X-GM-MSGID mapping is no longer needed after initial sync
        rm_cache("_".join([user.g_email, folder, "server_g_msgids"]))
        # XXX TODO: check for consistency with datastore here before
        # committing state: download any missing messages, delete any
        # messages that we have that the server doesn't. that way, worst case
        # if sync engine bugs trickle through is we lose some flags.
        log.info("Saved all messages and metadata on {0} to UIDVALIDITY {1} / HIGHESTMODSEQ {2}".format(folder, crispin_client.selected_uidvalidity,
            crispin_client.selected_highestmodseq))

    log.info("Finished.")

class SyncException(Exception): pass

def notify(user, mtype, message):
    """ Pass a message on to the notification dispatcher which deals with
        pubsub stuff.
    """
    # log.info("message from {0}: [{1}] {2}".format(user.g_email, mtype, message))

class SyncMonitor(Greenlet):
    def __init__(self, user, status_callback, n=5):
        self.user = user
        self.n = n
        self.status_callback = status_callback
        self.inbox = Queue()
        Greenlet.__init__(self)

    def _run(self):
        action = Greenlet.spawn(self.action)
        while not action.ready():
            try:
                cmd = self.inbox.get_nowait()
                if not self.process_command(cmd):
                    log.info("Stopping sync for {0}".format(self.user.g_email))
                    kill(action)
                    return
            except Empty: sleep(1)

    def process_command(self, cmd):
        """ Returns True if successful, or False if process should abort. """
        log.info("processing command {0}".format(cmd))
        return cmd != 'shutdown'

    def action(self):
        while not self.user.initial_sync_done:
            self.initial_sync()

        self.status_callback(self.user, 'poll', None)

        polling = True  # FOREVER
        while polling:
            self.poll()
            sleep(0)

    def initial_sync(self):
        updates = Queue()
        process = Greenlet.spawn(initial_sync, self.user, updates)
        progress = 0
        while not process.ready():
            self.status_callback(self.user, 'initial sync', progress)
            # XXX TODO wrap this in a Timeout in case the process crashes
            progress = updates.get()
            # let monitor accept commands
            sleep(0)
        # process may have finished with some progress left to
        # report; only report the last update
        remaining = [updates.get() for i in xrange(updates.qsize())]
        if remaining:
            self.status_callback(self.user, 'initial sync', remaining[-1])
        if process.successful():
            # we don't do this in initial_sync() to avoid confusion
            # with refreshing the self.user sqlalchemy object
            self.user.initial_sync_done = True
            db_session.add(self.user)
            db_session.commit()
        else:
            log.warning("initial sync for {0} failed: {1}".format(
                self.user.g_email, process.exception))
        assert updates.empty(), "initial sync completed for {0} with {1} progress items left to report: {2}".format(self.user.g_email, updates.qsize(), [updates.get() for i in xrange(updates.qsize())])

    def poll(self):
        log.info("polling {0}".format(self.user.g_email))
        process = Greenlet.spawn(incremental_sync, self.user)
        while not process.ready():
            sleep(0)
        if process.successful():
            self.status_callback(self.user, 'poll', datetime.utcnow().isoformat())
        else:
            log.warning("incremental update for {0} failed: {1}".format(
                self.user.g_email, process.exception))
        sleep(self.n)

class SyncService:
    """ ZeroRPC interface to syncing. """
    def __init__(self):
        # {'christine.spang@gmail.com': SyncMonitor()}
        self.monitors = dict()
        # READ ONLY from API calls, writes happen from callbacks from monitor
        # greenlets.
        # { 'user_id': { 'state': 'initial sync', 'status': '0'} }
        # 'state' can be ['initial sync', 'poll']
        # 'status' is the percent-done for initial sync, polling start time otherwise
        # all data in here ought to be msgpack-serializable!
        self.user_statuses = dict()

        # Restart existing active syncs. (Later we will want to partition
        # these across different machines, probably.)
        user_email_addresses = [r[0] for r in \
                db_session.query(User.g_email).filter_by(sync_active=True)]
        for user_email_address in user_email_addresses:
            log.info("Restarting sync for {0}".format(user_email_address))
            self.start_sync(user_email_address)

    def start_sync(self, user_email_address):
        try:
            user = db_session.query(User).filter_by(g_email=user_email_address).one()
            fqdn = socket.getfqdn()
            if user.sync_host is not None and user.sync_host != fqdn:
                return "WARNING syncing on different host"
            if user.g_email not in self.monitors:
                user.sync_lock()
                def update_user_status(user, state, status):
                    """ I really really wish I were a lambda """
                    self.user_statuses[user.id] = dict(
                            state=state, status=status)
                    notify(user, state, status)

                monitor = SyncMonitor(user, update_user_status)
                self.monitors[user.g_email] = monitor
                monitor.start()
                user.sync_active = True
                user.sync_host = socket.getfqdn()
                db_session.add(user)
                db_session.commit()
                return "OK sync started"
            else:
                return "OK sync already started"
        except sqlalchemy.orm.exc.NoResultFound:
            raise SyncException("No such user")

    def stop_sync(self, user_email_address):
        try:
            user = db_session.query(User).filter_by(g_email=user_email_address).one()
            if not user.sync_active:
                return "OK sync stopped already"
            fqdn = socket.getfqdn()
            assert user.sync_host == fqdn, "sync host FQDN doesn't match"
            # XXX Can processing this command fail in some way?
            self.monitors[user_email_address].inbox.put_nowait("shutdown")
            user.sync_active = False
            user.sync_host = None
            db_session.add(user)
            db_session.commit()
            user.sync_unlock()
            return "OK sync stopped"
        except sqlalchemy.orm.exc.NoResultFound:
            raise SyncException("No such user")

    def sync_status(self, user_email_address):
        return self.user_statuses.get(user_email_address)

    # XXX this should require some sort of auth or something, used from the
    # admin panel
    def status(self):
        return self.user_statuses
