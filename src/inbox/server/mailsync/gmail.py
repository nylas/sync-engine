"""
-----------------
GMAIL SYNC ENGINE
-----------------

Gmail is theoretically an IMAP backend, but it differs enough from standard
IMAP that we handle it differently. The state-machine rigamarole noted in
.imap.py applies, but we change a lot of the internal algorithms to fit Gmail's
structure.

Gmail has server-side threading, labels, and all messages are a subset of the
"All Mail" folder.

The only way to delete messages permanently on Gmail is to move a message to
the trash folder and then EXPUNGE.

We use Gmail's thread IDs locally, and download all mail via the All Mail
folder. We expand threads when downloading folders other than All Mail so the
user always gets the full thread when they look at mail.
"""
from __future__ import division

import os

from geventconnpool import retry

from .imap import uidvalidity_cb, new_or_updated, remove_deleted_uids
from .imap import chunked_uid_download, update_metadata, resync_uids_from
from .imap import base_initial_sync, base_poll, safe_download, commit_uids
from .imap import create_db_objects, ImapSyncMonitor

from ..models import imapaccount as account
from ..models.tables import ImapAccount, Namespace, ImapUid, Message

from inbox.util.itert import chunk, partition
from inbox.util.cache import set_cache, get_cache, rm_cache

class GmailSyncMonitor(ImapSyncMonitor):
    def __init__(self, account_id, namespace_id, email_address, provider,
            status_cb, heartbeat=1, poll_frequency=30):
        self.folder_state_handlers = {
                    'initial': initial_sync,
                    'initial uidinvalid': resync_uids_from('initial'),
                    'poll': poll,
                    'poll uidinvalid': resync_uids_from('poll'),
                    'finish': lambda c, s, l, f, st: 'finish',
                }

        ImapSyncMonitor.__init__(self, account_id, namespace_id, email_address,
                provider, status_cb, heartbeat=1, poll_frequency=30)
@retry
def initial_sync(crispin_client, db_session, log, folder_name, shared_state):
    return base_initial_sync(crispin_client, db_session, log, folder_name,
            shared_state, gmail_initial_sync)

def gmail_initial_sync(crispin_client, db_session, log, folder_name,
        shared_state, local_uids, c):
    remote_g_metadata = get_g_metadata(crispin_client, db_session, log,
            folder_name, local_uids, shared_state['syncmanager_lock'], c)
    remote_uids = sorted(remote_g_metadata.keys(), key=int)
    log.info("Found {0} UIDs for folder {1}".format(len(remote_uids),
        folder_name))
    if folder_name == crispin_client.folder_names(c)['all']:
        log.info("Already have {0} UIDs".format(len(local_uids)))

    local_uids = set(local_uids) - remove_deleted_uids(
            crispin_client.account_id, db_session, log, folder_name,
            local_uids, remote_uids, shared_state['syncmanager_lock'], c)

    unknown_uids = set(remote_uids) - set(local_uids)

    if folder_name != crispin_client.folder_names(c)['all']:
        chunked_thread_download(crispin_client, db_session, log, folder_name,
                remote_g_metadata, unknown_uids, shared_state['status_cb'],
                shared_state['syncmanager_lock'], c)
    else:
        full_download = deduplicate_message_download(crispin_client,
                db_session, log, remote_g_metadata, unknown_uids, c)
        chunked_uid_download(crispin_client, db_session, log, folder_name,
                full_download, len(local_uids), len(remote_uids),
                shared_state['status_cb'], shared_state['syncmanager_lock'],
                gmail_download_and_commit_uids,
                account.create_gmail_message, c)

    # Complete X-GM-MSGID mapping is no longer needed after initial sync.
    rm_cache(remote_g_metadata_cache_file(crispin_client.account_id, folder_name))

@retry
def poll(crispin_client, db_session, log, folder_name, shared_state):
    return base_poll(crispin_client, db_session, log, folder_name,
            shared_state, gmail_highestmodseq_update)

def gmail_highestmodseq_update(crispin_client, db_session, log, folder_name,
        uids, local_uids, status_cb, syncmanager_lock, c):
    local_g_metadata = account.g_metadata(crispin_client.account_id,
            db_session, folder_name)
    local_g_metadata.update(crispin_client.g_metadata(uids, c))

    if folder_name != crispin_client.folder_names(c)['all']:
        chunked_thread_download(crispin_client, db_session, log, folder_name,
                local_g_metadata, local_uids, status_cb, syncmanager_lock, c)

def remote_g_metadata_cache_file(account_id, folder_name):
    return os.path.join(str(account_id), folder_name, "remote_g_metadata")

def get_g_metadata(crispin_client, db_session, log, folder_name, uids,
        syncmanager_lock, c):
    account_id = crispin_client.account_id
    remote_g_metadata = None
    saved_validity = account.get_uidvalidity(account_id, db_session,
            folder_name)
    if saved_validity is not None:
        # If there's no cached validity we probably haven't run before.
        remote_g_metadata = retrieve_saved_g_metadata(crispin_client,
                db_session, log, folder_name, uids, saved_validity,
                syncmanager_lock, c)

    if remote_g_metadata is None:
        remote_g_metadata = crispin_client.g_metadata(
                crispin_client.all_uids(c), c)
        set_cache(remote_g_metadata_cache_file(account_id, folder_name),
                remote_g_metadata)
        # Save highestmodseq that corresponds to the saved g_metadata.
        account.update_uidvalidity(account_id, db_session, folder_name,
                crispin_client.selected_uidvalidity,
                crispin_client.selected_highestmodseq)
        db_session.commit()

    return remote_g_metadata

def gmail_download_and_commit_uids(crispin_client, db_session, log, folder_name,
        uids, msg_create_fn, syncmanager_lock, c):
    raw_messages = safe_download(crispin_client, log, uids, c)
    with syncmanager_lock:
        # there is the possibility that another green thread has already
        # downloaded some message(s) from this batch... check within the lock
        raw_messages = deduplicate_message_object_creation(
                crispin_client.account_id, db_session, log, raw_messages)
        new_imapuids = create_db_objects(crispin_client.account_id, db_session,
                log, folder_name, raw_messages, msg_create_fn)
        commit_uids(db_session, log, new_imapuids)
    return len(new_imapuids)

def chunked_thread_download(crispin_client, db_session, log, folder_name,
        g_metadata, uids, status_cb, syncmanager_lock, c):
    """ UIDs and g_metadata passed in are for the _folder that threads are
        being expanded in_.

        Messages are downloaded by thread, most-recent-thread-first,
        newest-to-oldest in thread. (Threads are expanded to all messages in
        the email archive that belong to the threads corresponding to the
        given uids.

        NOTE: this method will leave All Mail selected, since selecting
        folders is expensive and we don't want to assume what the caller
        needs to do next.
    """
    # X-GM-THRID is roughly ascending over time, so sort most-recent first
    all_g_thrids = sorted(set([msg['thrid'] for uid, msg in \
            g_metadata.iteritems() if uid in uids]), reverse=True)
    folder_g_msgids = {msg['msgid'] for uid, msg in g_metadata.items() \
            if uid in uids}
    log.info("{0} threads found".format(len(all_g_thrids)))

    flags = crispin_client.flags(uids, c)

    crispin_client.select_folder(
            crispin_client.folder_names(c)['all'],
            uidvalidity_cb(db_session,
                crispin_client.account_id), c)

    log.info("Expanding threads and downloading messages.")

    # We can't determine how many threads we have fully downloaded locally
    # before expansion, so we start from 0 every time and skip
    # already-downloaded messages along the way.
    num_downloaded_threads = 0
    num_total_threads = len(all_g_thrids)
    acc = db_session.query(ImapAccount).join(Namespace).filter_by(
            id=crispin_client.account_id).one()
    for g_thrids in chunk(all_g_thrids, 100):
        num_downloaded_threads = download_threads(crispin_client, db_session,
                log, acc, folder_name, g_thrids, flags, folder_g_msgids,
                num_downloaded_threads, num_total_threads, status_cb,
                syncmanager_lock, c)

def group_uids_by_thread(uids, thread_g_metadata):
    uids_for = dict()
    for uid in uids:
        uids_for.setdefault(thread_g_metadata[uid]['thrid'], []).append(uid)
    return uids_for

def create_original_folder_imapuids(acc, folder_name, imapuids,
        original_uid_for, flags):
    original_imapuids = []
    for item in imapuids:
        original_uid = original_uid_for[item.message.g_msgid]
        original_imapuid = ImapUid(
                imapaccount=acc, folder_name=folder_name,
                msg_uid=original_uid, message=item.message)
        original_imapuid.update_flags(
                flags[original_uid]['flags'],
                flags[original_uid]['labels'])
        original_imapuids.append(original_imapuid)
    return original_imapuids

def download_threads(crispin_client, db_session, log, acc, folder_name,
        g_thrids, flags, folder_g_msgids, num_downloaded_threads,
        num_total_threads, status_cb, syncmanager_lock, c):
    thread_uids = crispin_client.expand_threads(g_thrids, c)
    # need X-GM-MSGID in order to dedupe download and X-GM-THRID to sort
    thread_g_metadata = crispin_client.g_metadata(thread_uids, c)
    to_download = deduplicate_message_download(crispin_client, db_session, log,
            thread_g_metadata, thread_uids, c)
    log.info("need to get {0} deduplicated messages".format(len(to_download)))
    uids_for = group_uids_by_thread(to_download, thread_g_metadata)
    log.info("{0} threads after deduplication".format(len(uids_for)))
    num_downloaded_threads += (len(g_thrids) - len(uids_for))
    # download one thread at a time, most recent thread first
    # XXX we may want to chunk this download for large threads...
    for g_thrid in sorted(uids_for.keys(), reverse=True):
        percent_done = (num_downloaded_threads / num_total_threads) * 100
        status_cb(crispin_client.account_id, 'initial',
                (folder_name, percent_done))
        log.info("Syncing %s -- %.2f%% (%i/%i)" % (
            folder_name, percent_done,
            num_downloaded_threads, num_total_threads))
        uids = uids_for[g_thrid]
        log.info("downloading thread {0} with {1} messages" \
                .format(g_thrid, len(uids)))
        gmail_download_and_commit_uids(crispin_client, db_session, log,
                crispin_client.selected_folder_name, sorted(uids, reverse=True),
                account.create_gmail_message, syncmanager_lock, c)
        num_downloaded_threads += 1
    return num_downloaded_threads

def deduplicate_message_object_creation(account_id, db_session, log,
        raw_messages):
    new_g_msgids = {msg[5] for msg in raw_messages}
    existing_g_msgids = set(account.g_msgids(account_id, db_session,
        in_=new_g_msgids))
    return [msg for msg in raw_messages if msg[5] not in existing_g_msgids]

def deduplicate_message_download(crispin_client, db_session, log,
        remote_g_metadata, uids, c):
    """ Deduplicate message download using X-GM-MSGID. """
    local_g_msgids = set(account.g_msgids(crispin_client.account_id,
        db_session, in_=[remote_g_metadata[uid]['msgid'] for uid in uids]))
    full_download, imapuid_only = partition(
            lambda uid: remote_g_metadata[uid]['msgid'] in local_g_msgids,
            sorted(uids, key=int))
    log.info("Skipping {0} uids already downloaded".format(len(imapuid_only)))
    if len(imapuid_only) > 0:
        add_new_imapuid(crispin_client, db_session, remote_g_metadata,
                imapuid_only, c)

    return full_download

def add_new_imapuid(crispin_client, db_session, remote_g_metadata, uids, c):
    """ Since we deduplicate messages on Gmail, sometimes we need to just add
        new ImapUid entries.
    """
    flags = crispin_client.flags(uids, c)

    # Since we prioritize download for messages in certain threads, we may
    # already have ImapUid entries despite calling this method.
    local_folder_uids = {uid for uid, in \
            db_session.query(ImapUid.msg_uid).filter(
                ImapUid.folder_name==crispin_client.selected_folder_name,
                ImapUid.msg_uid.in_(uids))}
    uids = [uid for uid in uids if uid not in local_folder_uids]

    if uids:
        # collate message objects to relate the new imapuids
        imapuid_uid_for = dict([(metadata['msgid'], uid) for \
                (uid, metadata) in remote_g_metadata.items() if uid in uids])
        imapuid_g_msgids = [remote_g_metadata[uid]['msgid'] for uid in uids]
        message_for = dict([(imapuid_uid_for[mm.g_msgid], mm) for \
                mm in db_session.query(Message).filter( \
                    Message.g_msgid.in_(imapuid_g_msgids))])

        acc = db_session.query(ImapAccount).join(Namespace).filter_by(
                id=crispin_client.account_id).one()
        new_imapuids = [ImapUid(imapaccount=acc,
                    folder_name=crispin_client.selected_folder_name,
                    msg_uid=uid, message=message_for[uid]) for uid in uids]
        for item in new_imapuids:
            item.update_flags(flags[item.msg_uid]['flags'],
                    flags[item.msg_uid]['labels'])
        db_session.add_all(new_imapuids)
        db_session.commit()

def retrieve_saved_g_metadata(crispin_client, db_session, log, folder_name,
        local_uids, saved_validity, syncmanager_lock, c):
    log.info('Attempting to retrieve remote_g_metadata from cache')
    remote_g_metadata = get_cache(remote_g_metadata_cache_file(
        crispin_client.account_id, folder_name))
    if remote_g_metadata is not None:
        log.info("Successfully retrieved remote_g_metadata cache")
        if crispin_client.selected_highestmodseq > \
                saved_validity.highestmodseq:
            update_saved_g_metadata(crispin_client, db_session, log,
                    folder_name, remote_g_metadata, local_uids,
                    syncmanager_lock, c)
    else:
        log.info("No cached data found")
    return remote_g_metadata

def update_saved_g_metadata(crispin_client, db_session, log, folder_name,
        remote_g_metadata, local_uids, syncmanager_lock, c):
    """ If HIGHESTMODSEQ has changed since we saved the X-GM-MSGID cache,
        we need to query for any changes since then and update the saved
        data.
    """
    log.info("Updating cache with latest changes")
    # any uids we don't already have will be downloaded correctly
    # as usual, but updated uids need to be updated manually
    # XXX it may actually be faster to just query for X-GM-MSGID for the
    # whole folder rather than getting changed UIDs first; MODSEQ queries
    # are slow on large folders.
    modified = crispin_client.new_and_updated_uids(
            crispin_client.selected_highestmodseq, c)
    new, updated = new_or_updated(modified, local_uids)
    log.info("{0} new and {1} updated UIDs".format(len(new), len(updated)))
    # for new, query metadata and update cache
    remote_g_metadata.update(crispin_client.g_metadata(new, c))
    # filter out messages that have disappeared
    all_uids = set(crispin_client.all_uids(c))
    remote_g_metadata = dict((uid, md) for uid, md in \
            remote_g_metadata.iteritems() if uid in all_uids)
    set_cache(remote_g_metadata_cache_file(crispin_client.account_id,
        folder_name), remote_g_metadata)
    log.info("Updated cache with new messages")
    # for updated, it's easier to just update them now
    # bigger chunk because the data being fetched here is very small
    for uids in chunk(updated, 5*crispin_client.CHUNK_SIZE):
        update_metadata(crispin_client, db_session, log, folder_name, uids,
                syncmanager_lock, c)
    log.info("Updated metadata for modified messages")
