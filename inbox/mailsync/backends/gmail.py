"""
-----------------
GMAIL SYNC ENGINE
-----------------

Gmail is theoretically an IMAP backend, but it differs enough from standard
IMAP that we handle it differently. The state-machine rigamarole noted in
.imap.py applies, but we change a lot of the internal algorithms to fit Gmail's
structure.

Gmail has server-side threading, labels, and all messages are a subset of the
'All Mail' folder.

The only way to delete messages permanently on Gmail is to move a message to
the trash folder and then EXPUNGE.

We use Gmail's thread IDs locally, and download all mail via the All Mail
folder. We expand threads when downloading folders other than All Mail so the
user always gets the full thread when they look at mail.

"""
from __future__ import division

import os

from collections import namedtuple

from gevent import spawn
from gevent.queue import LifoQueue

from inbox.util.itert import chunk, partition
from inbox.util.cache import set_cache, get_cache, rm_cache
from inbox.util.misc import or_none

from inbox.contacts.process_mail import update_contacts
from inbox.crispin import (GMetadata, connection_pool, retry_crispin,
                           GmailSettingError)
from inbox.models.session import session_scope
from inbox.models.util import reconcile_message
from inbox.models import Message, Folder
from inbox.models.backends.gmail import GmailAccount
from inbox.models.backends.imap import ImapUid, ImapThread
from inbox.mailsync.backends.base import (create_db_objects,
                                          commit_uids, new_or_updated,
                                          MailsyncError)
from inbox.mailsync.backends.imap import (account, uidvalidity_cb,
                                          remove_deleted_uids,
                                          download_queued_uids,
                                          update_metadata, resync_uids_from,
                                          base_initial_sync,
                                          condstore_base_poll, safe_download,
                                          add_uids_to_stack, check_new_uids,
                                          uid_list_to_stack, report_progress,
                                          ImapSyncMonitor, update_uid_counts)


PROVIDER = 'gmail'
SYNC_MONITOR_CLS = 'GmailSyncMonitor'

GMessage = namedtuple('GMessage', 'uid g_metadata flags labels')


class GmailSyncMonitor(ImapSyncMonitor):
    def __init__(self, account_id, namespace_id, email_address, provider_name,
                 heartbeat=1, poll_frequency=300):
        self.folder_state_handlers = {
            'initial': initial_sync,
            'initial uidinvalid': resync_uids_from('initial'),
            'poll': poll,
            'poll uidinvalid': resync_uids_from('poll'),
            'finish': lambda c, s, l, f, st: 'finish',
        }

        ImapSyncMonitor.__init__(self, account_id, namespace_id, email_address,
                                 provider_name, heartbeat=1,
                                 poll_frequency=poll_frequency,
                                 retry_fail_classes=[GmailSettingError])


@retry_crispin
def initial_sync(conn_pool, log, folder_name, shared_state):
    with conn_pool.get() as crispin_client:
        return base_initial_sync(crispin_client, log, folder_name,
                                 shared_state, gmail_initial_sync,
                                 create_gmail_message)


def uid_download_folders(crispin_client):
    """ Folders that don't get thread-expanded. """
    return [crispin_client.folder_names()[tag] for tag in
            ('trash', 'spam', 'all') if tag in crispin_client.folder_names()]


def gmail_initial_sync(crispin_client, log, folder_name, shared_state,
                       local_uids, uid_download_stack, msg_create_fn):
    remote_uid_count = len(set(crispin_client.all_uids()))
    remote_g_metadata, update_uid_count = get_g_metadata(
        crispin_client, log, folder_name, local_uids,
        shared_state['syncmanager_lock'])
    remote_uids = sorted(remote_g_metadata.keys(), key=int)
    log.info(remote_uid_count=len(remote_uids))
    if folder_name == crispin_client.folder_names()['all']:
        log.info(local_uid_count=len(local_uids))

    with shared_state['syncmanager_lock']:
        log.debug('gmail_initial_sync grabbed syncmanager_lock')
        with session_scope(ignore_soft_deletes=False) as db_session:
            deleted_uids = remove_deleted_uids(
                crispin_client.account_id, db_session, log, folder_name,
                local_uids, remote_uids)
            delete_uid_count = len(deleted_uids)

            local_uids = set(local_uids) - deleted_uids
            unknown_uids = set(remote_uids) - local_uids

            # Persist the num(messages) to sync (any type of sync: download,
            # update or delete) before we start.
            # Note that num_local_deleted, num_local_updated ARE the numbers to
            # delete/update too since we make those changes rightaway before we
            # start downloading messages.
            update_uid_counts(db_session, log, crispin_client.account_id,
                              folder_name, remote_uid_count=remote_uid_count,
                              download_uid_count=len(unknown_uids),
                              update_uid_count=update_uid_count,
                              delete_uid_count=delete_uid_count)

    if folder_name == crispin_client.folder_names()['inbox']:
        # We don't do an initial dedupe for Inbox because we do thread
        # expansion, which means even if we have a given msgid downloaded, we
        # miiight not have the whole thread. This means that restarts cause
        # duplicate work, but hopefully these folders aren't too huge.
        message_download_stack = LifoQueue()
        flags = crispin_client.flags(unknown_uids)
        for uid in unknown_uids:
            if uid in flags:
                message_download_stack.put(
                    GMessage(uid, remote_g_metadata[uid], flags[uid].flags,
                             flags[uid].labels))
        new_uid_poller = spawn(check_new_g_thrids, crispin_client.account_id,
                               crispin_client.PROVIDER, folder_name, log,
                               message_download_stack,
                               shared_state['poll_frequency'],
                               shared_state['syncmanager_lock'])
        download_queued_threads(crispin_client, log, folder_name,
                                message_download_stack,
                                shared_state['syncmanager_lock'])
    elif folder_name in uid_download_folders(crispin_client):
        full_download = deduplicate_message_download(
            crispin_client, log, shared_state['syncmanager_lock'],
            remote_g_metadata, unknown_uids)
        add_uids_to_stack(full_download, uid_download_stack)
        new_uid_poller = spawn(check_new_uids, crispin_client.account_id,
                               folder_name,
                               log, uid_download_stack,
                               shared_state['poll_frequency'],
                               shared_state['syncmanager_lock'])
        download_queued_uids(crispin_client, log, folder_name,
                             uid_download_stack, len(local_uids),
                             len(unknown_uids),
                             shared_state['syncmanager_lock'],
                             gmail_download_and_commit_uids, msg_create_fn)
    else:
        raise MailsyncError(
            'Unknown Gmail sync folder: {}'.format(folder_name))

    # Complete X-GM-MSGID mapping is no longer needed after initial sync.
    rm_cache(remote_g_metadata_cache_file(crispin_client.account_id,
                                          folder_name))

    new_uid_poller.kill()


@retry_crispin
def poll(conn_pool, log, folder_name, shared_state):
    with conn_pool.get() as crispin_client:
        return condstore_base_poll(crispin_client, log, folder_name,
                                   shared_state, gmail_highestmodseq_update)


def gmail_highestmodseq_update(crispin_client, log, folder_name, uids,
                               local_uids, syncmanager_lock):
    g_metadata = crispin_client.g_metadata(uids)
    to_download = deduplicate_message_download(
        crispin_client, log, syncmanager_lock, g_metadata, uids)
    if folder_name == crispin_client.folder_names()['inbox']:
        flags = crispin_client.flags(to_download)
        message_download_stack = LifoQueue()
        for uid in to_download:
            if uid in flags and uid in g_metadata:
                # IMAP will just return no data for a UID if it's disappeared
                # from the folder in the meantime.
                message_download_stack.put(GMessage(
                    uid, g_metadata[uid], flags[uid].flags, flags[uid].labels))
        download_queued_threads(crispin_client, log, folder_name,
                                message_download_stack, syncmanager_lock)
    elif folder_name in uid_download_folders(crispin_client):
        uid_download_stack = uid_list_to_stack(to_download)
        download_queued_uids(crispin_client, log, folder_name,
                             uid_download_stack, 0, uid_download_stack.qsize(),
                             syncmanager_lock, gmail_download_and_commit_uids,
                             create_gmail_message)
    else:
        raise MailsyncError(
            'Unknown Gmail sync folder: {}'.format(folder_name))


def remote_g_metadata_cache_file(account_id, folder_name):
    return os.path.join(str(account_id), folder_name, 'remote_g_metadata')


def get_g_metadata(crispin_client, log, folder_name, uids, syncmanager_lock):
    assert folder_name == crispin_client.selected_folder_name, \
        "crispin selected folder isn't as expected"
    account_id = crispin_client.account_id
    remote_g_metadata = None
    update_uid_count = 0

    with session_scope(ignore_soft_deletes=False) as db_session:
        saved_folder_info = account.get_folder_info(
            account_id, db_session, folder_name)
        saved_highestmodseq = or_none(saved_folder_info, lambda i:
                                      i.highestmodseq)
    if saved_highestmodseq is not None:
        # If there's no cached validity we probably haven't run before.
        remote_g_metadata, update_uid_count = retrieve_saved_g_metadata(
            crispin_client, log, folder_name, uids,
            saved_highestmodseq, syncmanager_lock)

    if remote_g_metadata is None:
        remote_g_metadata = crispin_client.g_metadata(
            crispin_client.all_uids())
        set_cache(remote_g_metadata_cache_file(account_id, folder_name),
                  remote_g_metadata)
        # Save highestmodseq that corresponds to the saved g_metadata.
    with session_scope(ignore_soft_deletes=False) as db_session:
        account.update_folder_info(account_id, db_session, folder_name,
                                   crispin_client.selected_uidvalidity,
                                   crispin_client.selected_highestmodseq)
        db_session.commit()

    return remote_g_metadata, update_uid_count


def gmail_download_and_commit_uids(crispin_client, log, folder_name, uids,
                                   msg_create_fn, syncmanager_lock):
    log.info('downloading uids', uids=uids)
    raw_messages = safe_download(crispin_client, log, uids)
    with syncmanager_lock:
        log.info('gmail_download_and_commit_uids acquired syncmanager_lock')
        # there is the possibility that another green thread has already
        # downloaded some message(s) from this batch... check within the lock
        with session_scope(ignore_soft_deletes=False) as db_session:
            raw_messages = deduplicate_message_object_creation(
                crispin_client.account_id, db_session, log, raw_messages)
            log.info(unsaved_message_object_count=len(raw_messages))
            new_imapuids = create_db_objects(
                crispin_client.account_id, db_session, log, folder_name,
                raw_messages, msg_create_fn)
            commit_uids(db_session, log, new_imapuids)
            log.info(new_committed_message_count=len(new_imapuids))
    return len(new_imapuids)


def check_new_g_thrids(account_id, provider_name, folder_name, log,
                       message_download_stack, poll_frequency,
                       syncmanager_lock):
    """
    Check for new X-GM-THRIDs and add them to the download stack.

    We do this by comparing local UID lists to remote UID lists, maintaining
    the invariant that (stack uids)+(local uids) == (remote uids).

    We also remove local messages that have disappeared from the remote, since
    it's totally probable that users will be archiving mail as the initial
    sync goes on.

    We grab a new IMAP connection from the pool for this to isolate its
    actions from whatever the main greenlet may be doing.

    Runs until killed. (Intended to be run in a greenlet.)

    """
    with connection_pool(account_id).get() as crispin_client:
        crispin_client.select_folder(folder_name,
                                     uidvalidity_cb(crispin_client.account_id))
        while True:
            log.info('Checking for new/deleted messages during initial sync.')
            remote_uids = set(crispin_client.all_uids())
            # We lock this section to make sure no messages are being modified
            # in the database while we make sure the queue is in a good state.
            with syncmanager_lock:
                log.debug('check_new_g_thrids acquired syncmanager_lock')
                with session_scope(ignore_soft_deletes=False) as db_session:
                    local_uids = set(account.all_uids(account_id, db_session,
                                                      folder_name))
                    stack_uids = {gm.uid for gm in
                                  message_download_stack.queue}
                    local_with_pending_uids = local_uids | stack_uids
                    deleted_uids = remove_deleted_uids(
                        account_id, db_session, log, folder_name, local_uids,
                        remote_uids)
                    log.info(deleted_uid_count=len(deleted_uids))

                # filter out messages that have disappeared on the remote side
                new_message_download_stack = [gm for gm in
                                              message_download_stack.queue
                                              if gm.uid in remote_uids]

                # add in any new uids from the remote
                new_uids = [uid for uid in remote_uids if uid not in
                            local_with_pending_uids]
                flags = crispin_client.flags(new_uids)
                g_metadata = crispin_client.g_metadata(new_uids)
                log.info('adding new messages to download queue',
                         count=min(len(flags), len(g_metadata)))
                for new_uid in new_uids:
                    # could have disappeared from the folder in the meantime
                    if new_uid in flags and new_uid in g_metadata:
                        new_message_download_stack.append(
                            GMessage(new_uid, g_metadata[new_uid],
                                     flags[new_uid].flags,
                                     flags[new_uid].labels))
                message_download_stack.queue = sorted(
                    new_message_download_stack, key=lambda m: m.uid)

            log.info('idling', timeout=poll_frequency)
            crispin_client.conn.idle()
            crispin_client.conn.idle_check(timeout=poll_frequency)
            crispin_client.conn.idle_done()
            log.info('IDLE detected changes or timeout reached')


def download_queued_threads(crispin_client, log, folder_name,
                            message_download_stack, syncmanager_lock):
    """
    Download threads until `message_download_stack` is empty.

    UIDs and g_metadata that come out of `message_download_stack` are for
    the _folder that threads are being expanded in_.

    Threads are downloaded in the order they come out of the stack, which
    _ought_ to be putting newest threads at the top. Messages are
    downloaded newest-to-oldest in thread. (Threads are expanded to all
    messages in the email archive that belong to the threads corresponding
    to the given uids.)

    """
    num_total_messages = message_download_stack.qsize()
    log.info(num_total_messages=num_total_messages)

    log.info('Expanding threads and downloading messages.')
    # We still need the original crispin connection for progress reporting,
    # so the easiest thing to do here with the current pooling setup is to
    # create a new crispin client for querying All Mail.
    with connection_pool(crispin_client.account_id).get() as \
            all_mail_crispin_client:
        all_mail_crispin_client.select_folder(
            crispin_client.folder_names()['all'],
            uidvalidity_cb(crispin_client.account_id))

        # Since we do thread expansion, for any given thread, even if we
        # already have the UID in the given GMessage downloaded, we may not
        # have _every_ message in the thread. We have to expand it and make
        # sure we have all messages.
        while not message_download_stack.empty():
            message = message_download_stack.get_nowait()
            # Don't try to re-download any messages that are in the same
            # thread. (Putting this _before_ the download to guarantee no
            # context switches happen in the meantime; we _should_ re-download
            # if another message arrives on the thread.)
            processed_msgs = [m for m in message_download_stack.queue if
                              m.g_metadata.thrid ==
                              message.g_metadata.thrid]
            processed_msgs.append(message)
            message_download_stack.queue = [
                m for m in message_download_stack.queue if m.g_metadata.thrid
                != message.g_metadata.thrid]
            thread_uids = all_mail_crispin_client.expand_threads(
                [message.g_metadata.thrid])
            thread_g_metadata = all_mail_crispin_client.g_metadata(
                thread_uids)
            download_thread(all_mail_crispin_client, log, syncmanager_lock,
                            thread_g_metadata, message.g_metadata.thrid,
                            thread_uids)
            # In theory we only ever have one Greenlet modifying ImapUid
            # entries for a non-All Mail folder, but grab the lock anyway
            # to be safe.
            with syncmanager_lock:
                log.debug('download_queued_threads acquired syncmanager_lock')
                # Since we download msgs from All Mail, we need to separately
                # make sure we have ImapUids recorded for this folder (used in
                # progress tracking, queuing, and delete detection).
                log.debug('adding imapuid rows', count=len(processed_msgs))
                with session_scope(ignore_soft_deletes=False) as db_session:
                    acc = db_session.query(GmailAccount).get(
                        crispin_client.account_id)
                    for msg in processed_msgs:
                        add_new_imapuid(db_session, log, msg, folder_name, acc)

            report_progress(crispin_client, log, folder_name,
                            len(processed_msgs),
                            message_download_stack.qsize())
        log.info('Message download queue emptied')
    # Intentionally don't report which UIDVALIDITY we've saved messages to
    # because we have All Mail selected and don't have the UIDVALIDITY for
    # the folder we're actually downloading messages for.


def download_thread(crispin_client, log, syncmanager_lock, thread_g_metadata,
                    g_thrid, thread_uids):
    """
    Download all messages in thread identified by `g_thrid`.

    Messages are downloaded most-recent-first via All Mail, which allows us to
    get the entire thread regardless of which folders it's in.

    """
    log.debug('downloading thread',
              g_thrid=g_thrid, message_count=len(thread_uids))
    to_download = deduplicate_message_download(
        crispin_client, log, syncmanager_lock, thread_g_metadata, thread_uids)
    log.debug(deduplicated_message_count=len(to_download))
    for uids in chunk(reversed(to_download), crispin_client.CHUNK_SIZE):
        gmail_download_and_commit_uids(crispin_client, log,
                                       crispin_client.selected_folder_name,
                                       uids, create_gmail_message,
                                       syncmanager_lock)
    return len(to_download)


def deduplicate_message_object_creation(account_id, db_session, log,
                                        raw_messages):
    log.info('Deduplicating message object creation.')
    new_g_msgids = {msg.g_msgid for msg in raw_messages}
    existing_g_msgids = set(account.g_msgids(account_id, db_session,
                                             in_=new_g_msgids))
    return [msg for msg in raw_messages if msg.g_msgid not in
            existing_g_msgids]


def deduplicate_message_download(crispin_client, log, syncmanager_lock,
                                 remote_g_metadata, uids):
    """
    Deduplicate message download using X-GM-MSGID.

    Returns
    -------
    list
        Deduplicated UIDs.

    """
    with session_scope(ignore_soft_deletes=False) as db_session:
        local_g_msgids = set(account.g_msgids(crispin_client.account_id,
                                              db_session,
                                              in_={remote_g_metadata[uid].msgid
                                                   for uid in uids if uid in
                                                   remote_g_metadata}))
    full_download, imapuid_only = partition(
        lambda uid: uid in remote_g_metadata and
        remote_g_metadata[uid].msgid in local_g_msgids,
        sorted(uids, key=int))
    if imapuid_only:
        log.info('skipping already downloaded uids', count=len(imapuid_only))
        # Since we always download messages via All Mail and create the
        # relevant All Mail ImapUids too at that time, we don't need to create
        # them again here if we're deduping All Mail downloads.
        if crispin_client.selected_folder_name != \
                crispin_client.folder_names()['all']:
            add_new_imapuids(crispin_client, log, remote_g_metadata,
                             syncmanager_lock, imapuid_only)

    return full_download


def add_new_imapuid(db_session, log, gmessage, folder_name, acc):
    """
    Add ImapUid object for this GMessage if we don't already have one.

    Parameters
    ----------
    message : GMessage
        Message to add ImapUid for.
    folder_name : str
        Which folder to add the ImapUid in.
    acc : GmailAccount
        Which account to associate the message with. (Not looking this up
        within this function is a db access optimization.)

    """
    if not db_session.query(ImapUid.msg_uid).join(Folder).filter(
            Folder.name == folder_name,
            ImapUid.account_id == acc.id,
            ImapUid.msg_uid == gmessage.uid).all():
        message = db_session.query(Message).join(ImapThread).filter(
            ImapThread.g_thrid == gmessage.g_metadata.thrid,
            Message.g_thrid == gmessage.g_metadata.thrid,
            Message.g_msgid == gmessage.g_metadata.msgid,
            ImapThread.namespace_id == acc.namespace.id).one()
        new_imapuid = ImapUid(
            account=acc,
            folder=Folder.find_or_create(db_session, acc, folder_name),
            msg_uid=gmessage.uid, message=message)
        new_imapuid.update_imap_flags(gmessage.flags, gmessage.labels)
        db_session.add(new_imapuid)
        db_session.commit()
    else:
        log.debug('skipping imapuid creation', uid=gmessage.uid)


def add_new_imapuids(crispin_client, log, remote_g_metadata, syncmanager_lock,
                     uids):
    """
    Add ImapUid entries only for (already-downloaded) messages.

    If a message has already been downloaded via another folder, we only need
    to add `ImapUid` accounting for the current folder. `Message` objects
    etc. have already been created.

    """
    flags = crispin_client.flags(uids)

    with syncmanager_lock:
        with session_scope(ignore_soft_deletes=False) as db_session:
            log.debug('add_new_imapuids acquired syncmanager_lock')
            # Since we prioritize download for messages in certain threads, we
            # may already have ImapUid entries despite calling this method.
            local_folder_uids = {uid for uid, in
                                 db_session.query(ImapUid.msg_uid).join(Folder)
                                 .filter(
                                     ImapUid.account_id ==
                                     crispin_client.account_id,
                                     Folder.name ==
                                     crispin_client.selected_folder_name,
                                     ImapUid.msg_uid.in_(uids))}
            uids = [uid for uid in uids if uid not in local_folder_uids]

            if uids:
                acc = db_session.query(GmailAccount).get(
                    crispin_client.account_id)

                # collate message objects to relate the new imapuids to
                imapuid_for = dict([(metadata.msgid, uid) for (uid, metadata)
                                    in remote_g_metadata.items()
                                    if uid in uids])
                imapuid_g_msgids = [remote_g_metadata[uid].msgid for uid in
                                    uids]
                message_for = dict([(imapuid_for[m.g_msgid], m) for m in
                                    db_session.query(Message).join(ImapThread)
                                    .filter(
                                        Message.g_msgid.in_(imapuid_g_msgids),
                                        ImapThread.namespace_id ==
                                        acc.namespace.id)])

                # Stop Folder.find_or_create()'s query from triggering a flush.
                with db_session.no_autoflush:
                    new_imapuids = [ImapUid(
                        account=acc,
                        folder=Folder.find_or_create(
                            db_session, acc,
                            crispin_client.selected_folder_name),
                        msg_uid=uid, message=message_for[uid]) for uid in uids]
                    for item in new_imapuids:
                        # skip uids which have disappeared in the meantime
                        if item.msg_uid in flags:
                            item.update_imap_flags(flags[item.msg_uid].flags,
                                                   flags[item.msg_uid].labels)
                db_session.add_all(new_imapuids)
                db_session.commit()


def retrieve_saved_g_metadata(crispin_client, log, folder_name, local_uids,
                              saved_highestmodseq, syncmanager_lock):
    log.info('Attempting to retrieve remote_g_metadata from cache')

    update_uid_count = 0
    remote_g_metadata = get_cache(remote_g_metadata_cache_file(
        crispin_client.account_id, folder_name))

    if remote_g_metadata is not None:
        # Rebuild namedtuples because msgpack
        remote_g_metadata = {k: GMetadata(*v) for k, v in
                             remote_g_metadata.iteritems()}

        log.info('successfully retrieved remote_g_metadata cache',
                 object_count=len(remote_g_metadata))
        if crispin_client.selected_highestmodseq > saved_highestmodseq:
            update_uid_count = update_saved_g_metadata(
                crispin_client, log, folder_name, remote_g_metadata,
                local_uids, syncmanager_lock)
    else:
        log.info("No cached data found")
    return remote_g_metadata, update_uid_count


def update_saved_g_metadata(crispin_client, log, folder_name,
                            remote_g_metadata, local_uids, syncmanager_lock):
    """
    If HIGHESTMODSEQ has changed since we saved the X-GM-MSGID cache,
    we need to query for any changes since then and update the saved
    data.

    """
    log.info('Updating cache with latest changes')
    # Any uids we don't already have will be downloaded correctly as usual, but
    # updated uids need to be updated manually.
    # XXX it may actually be faster to just query for X-GM-MSGID for the
    # whole folder rather than getting changed UIDs first; MODSEQ queries
    # are slow on large folders.
    modified = crispin_client.new_and_updated_uids(
        crispin_client.selected_highestmodseq)
    log.info(modified_msg_count=len(modified))
    new, updated = new_or_updated(modified, local_uids)
    log.info(new_uid_count=len(new), updated_uid_count=len(updated))
    if new:
        remote_g_metadata.update(crispin_client.g_metadata(new))
        log.info('Updated cache with new messages')
    else:
        log.info('No new messages to update metadata for')
    # Filter out messages that have disappeared.
    old_len = len(remote_g_metadata)
    current_remote_uids = set(crispin_client.all_uids())
    remote_g_metadata = dict((uid, md) for uid, md in
                             remote_g_metadata.iteritems() if uid in
                             current_remote_uids)
    num_removed = old_len - len(remote_g_metadata)
    if num_removed > 0:
        log.info(removed_msg_count=num_removed)
    set_cache(remote_g_metadata_cache_file(crispin_client.account_id,
                                           folder_name), remote_g_metadata)
    if updated:
        # It's easy and fast to just update these here and now.
        # Bigger chunk because the data being fetched here is very small.
        for uids in chunk(updated, 5 * crispin_client.CHUNK_SIZE):
            update_metadata(crispin_client, log, folder_name, uids,
                            syncmanager_lock)
        log.info('updated metadata for modified messages',
                 msg_count=len(updated))
        return len(updated)
    else:
        log.info('No modified messages to update metadata for')
        return 0


def create_gmail_message(db_session, log, acct, folder, msg):
    """ Gmail-specific message creation logic. """

    new_uid = account.create_imap_message(db_session, log, acct, folder, msg)

    new_uid = add_gmail_attrs(db_session, log, new_uid, msg.flags, folder,
                              msg.g_thrid, msg.g_msgid, msg.g_labels,
                              msg.created)

    update_contacts(db_session, acct.id, new_uid.message)
    return new_uid


def add_gmail_attrs(db_session, log, new_uid, flags, folder, g_thrid, g_msgid,
                    g_labels, created):
    """ Gmail-specific post-create-message bits. """
    # Disable autoflush so we don't try to flush a message with null
    # thread_id, causing a crash, and so that we don't flush on each
    # added/removed label.
    with db_session.no_autoflush:
        new_uid.message.g_msgid = g_msgid
        # NOTE: g_thrid == g_msgid on the first message in the thread :)
        new_uid.message.g_thrid = g_thrid
        new_uid.update_imap_flags(flags, g_labels)

        thread = new_uid.message.thread = ImapThread.from_gmail_message(
            db_session, new_uid.account.namespace, new_uid.message)

        # make sure this thread has all the correct labels
        new_labels = account.update_thread_labels(thread, folder.name,
                                                  g_labels, db_session)

        # Reconciliation for Drafts, Sent Mail folders:
        if (('draft' in new_labels or 'sent' in new_labels) and not
                created and new_uid.message.inbox_uid):
            reconcile_message(db_session, log, new_uid.message.inbox_uid,
                              new_uid.message)

        return new_uid
