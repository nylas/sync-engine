from __future__ import division

import socket

from .sessionmanager import get_crispin_from_email

from .models import db_session, FolderMeta, MessageMeta, UIDValidity
from .models import IMAPAccount, Block, SyncMeta
from sqlalchemy.orm.exc import NoResultFound

from ..util.itert import chunk, partition
from ..util.cache import set_cache, get_cache, rm_cache

from .log import configure_sync_logging, get_logger
log = get_logger()

from gc import collect as garbge_collect
from datetime import datetime

from gevent import Greenlet, sleep, joinall, kill
from gevent.queue import Queue, Empty

from .google_oauth import InvalidOauthGrantException

import encoding
import json
from itertools import chain
from quopri import decodestring as quopri_decodestring
from base64 import b64decode
from chardet import detect as detect_charset
from hashlib import sha256

"""
---------------
THE SYNC ENGINE
---------------

Okay, here's the deal.

The sync engine runs per-folder on each account. This allows behaviour like
the Inbox to receive new mail via polling while we're still running the initial
sync on a huge All Mail folder.

Only one initial sync can be running per-account at a time, to avoid
hammering the IMAP backend too hard (Gmail shards per-user, so parallelizing
folder download won't actually increase our throughput anyway).

Any time we reconnect, we have to make sure the folder's uidvalidity hasn't
changed, and if it has, we need to update the UIDs for any messages we've
already downloaded. A folder's uidvalidity cannot change during a session
(SELECT during an IMAP session starts a session on a folder).

Folder sync state is stored in the SyncMeta table to allow for restarts.

Here's the state machine:

----------------         ----------------------
- initial sync - <-----> - initial uidinvalid -
----------------         ----------------------
        ∧
        |
        ∨
----------------         ----------------------
-      poll    - <-----> -   poll uidinvalid  -
----------------         ----------------------
-  ∧
----

We encapsulate sync engine instances in greenlets for cooperative coroutine
scheduling around network I/O.

We provide a ZeroRPC service for starting, stopping, and querying status on
running syncs. We don't provide knobs to start/stop sync instances at a
per-folder level, only at a per-account level. There's no good reason to be
able to do so, and leaving that configurability out simplifies the interface.
"""

### exceptions

class SyncException(Exception): pass

### main

def refresh_crispin(email, dummy=False):
    try:
        return get_crispin_from_email(email, dummy)
    except InvalidOauthGrantException, e:
        log.error("Error refreshing crispin on {0} because {1}".format(email, e))
        raise e

def fetch_uidvalidity(account, folder_name):
    try:
        # using .one() here may catch duplication bugs
        return db_session.query(UIDValidity).filter_by(
                account=account, folder_name=folder_name).one()
    except NoResultFound:
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

def new_or_updated(uids, folder, account_id, local_uids=None):
    if local_uids is None:
        local_uids = set([unicode(uid) for uid, in \
                db_session.query(FolderMeta.msg_uid).filter(
                FolderMeta.folder_name==folder,
                FolderMeta.imapaccount_id==account_id,
                FolderMeta.msg_uid.in_(uids))])
    return partition(lambda x: x in local_uids, uids)

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

def process_messages(account, folder, messages):
    """ Parses message data for the given UIDs, creates metadata database
        entries and writes mail parts to disk.
    """
    new_messages = []
    new_foldermeta = []
    for uid, internaldate, flags, envelope, body, x_gm_thrid, x_gm_msgid, \
            x_gm_labels in messages:
        mailbase = encoding.from_string(body)
        new_msg = MessageMeta()
        new_msg.data_sha256 = sha256(body).hexdigest()
        new_msg.namespace_id = account.namespace.id
        new_msg.uid = uid
        # XXX maybe eventually we want to use these, but for
        # backcompat for now let's keep in the
        # new_msg.subject = mailbase.headers.get('Subject')
        # new_msg.from_addr = mailbase.headers.get('From')
        # new_msg.sender_addr = mailbase.headers.get('Sender')
        # new_msg.reply_to = mailbase.headers.get('Reply-To')
        # new_msg.to_addr = mailbase.headers.get('To')
        # new_msg.cc_addr = mailbase.headers.get('Cc')
        # new_msg.bcc_addr = mailbase.headers.get('Bcc')
        # new_msg.in_reply_to = mailbase.headers.get('In-Reply-To')
        # new_msg.message_id = mailbase.headers.get('Message-Id')

        def make_unicode_contacts(contact_list):
            if not contact_list: return None
            n = []
            for c in contact_list:
                new_c = [None]*len(c)
                for i in range(len(c)):
                    new_c[i] = encoding.make_unicode_header(c[i])
                n.append(new_c)
            return n

        tempSubject = encoding.make_unicode_header(envelope[1])
        # Headers will wrap when longer than 78 chars per RFC822_2
        tempSubject = tempSubject.replace('\n\t', '').replace('\r\n', '')
        new_msg.subject = tempSubject
        new_msg.from_addr = make_unicode_contacts(envelope[2])
        new_msg.sender_addr = make_unicode_contacts(envelope[3])
        new_msg.reply_to = envelope[4]
        new_msg.to_addr = make_unicode_contacts(envelope[5])
        new_msg.cc_addr = make_unicode_contacts(envelope[6])
        new_msg.bcc_addr = make_unicode_contacts(envelope[7])
        new_msg.in_reply_to = envelope[8]
        new_msg.message_id = envelope[9]

        new_msg.internaldate = internaldate
        new_msg.g_thrid = unicode(x_gm_thrid)
        new_msg.g_msgid = unicode(x_gm_msgid)

        fm = FolderMeta(imapaccount_id=account.id,
                folder_name=folder,
                msg_uid=uid, messagemeta=new_msg)
        new_foldermeta.append(fm)

        # TODO parse out flags and store as enum instead of string
        # \Seen  Message has been read
        # \Answered  Message has been answered
        # \Flagged  Message is "flagged" for urgent/special attention
        # \Deleted  Message is "deleted" for removal by later EXPUNGE
        # \Draft  Message has not completed composition (marked as a draft).
        # \Recent   session is the first session to have been notified about this message
        new_msg.flags = unicode(flags)

        new_msg.size = len(body)  # includes headers text

        new_messages.append(new_msg)

        i = 0  # for walk_index

        # Store all message headers as object with index 0
        headers_part = Block()
        headers_part.messagemeta = new_msg
        headers_part.walk_index = i
        headers_part._data = json.dumps(mailbase.headers)
        headers_part.data_sha256 = sha256(headers_part._data).hexdigest()
        new_msg.parts.append(headers_part)

        extra_parts = []

        if mailbase.body:
            # single-part message?
            extra_parts.append(mailbase)

        for part in chain(extra_parts, mailbase.walk()):
            i += 1
            mimepart = encoding.to_message(part)
            if mimepart.is_multipart(): continue  # TODO should we store relations?

            new_part = Block()
            new_part.messagemeta = new_msg
            new_part.walk_index = i
            new_part.misc_keyval = mimepart.items()  # everything

            # Content-Type
            try:
                assert mimepart.get_content_type() == mimepart.get_params()[0][0],\
                "Content-Types not equal!  %s and %s" (mimepart.get_content_type(), mimepart.get_params()[0][0])
            except Exception, e:
                log.error("Content-Types not equal: %s" % mimepart.get_params())

            new_part.content_type = mimepart.get_content_type()


            # File attachments
            filename = mimepart.get_filename(failobj=None)
            if filename: encoding.make_unicode_header(filename)
            new_part.filename = filename

            # Make sure MIME-Version is 1.0
            mime_version = mimepart.get('MIME-Version', failobj=None)
            if mime_version and mime_version != '1.0':
                log.error("Unexpected MIME-Version: %s" % mime_version)

            # Content-Disposition attachment; filename="floorplan.gif"
            content_disposition = mimepart.get('Content-Disposition', None)
            if content_disposition:
                parsed_content_disposition = content_disposition.split(';')[0].lower()
                if parsed_content_disposition not in ['inline', 'attachment']:
                    errmsg = """
Unknown Content-Disposition on message {0} found in {1}.
Original Content-Disposition was: '{2}'
Parsed Content-Disposition was: '{3}'""".format(uid, folder,
                        content_disposition, parsed_content_disposition)
                    log.error(errmsg)
                else:
                    new_part.content_disposition = parsed_content_disposition

            new_part.content_id = mimepart.get('Content-Id', None)

            # DEBUG -- not sure if these are ever really used in emails
            if mimepart.preamble:
                log.warning("Found a preamble! " + mimepart.preamble)
            if mimepart.epilogue:
                log.warning("Found an epilogue! " + mimepart.epilogue)

            payload_data = mimepart.get_payload(decode=False)  # decode ourselves
            data_encoding = mimepart.get('Content-Transfer-Encoding', None).lower()

            if data_encoding == 'quoted-printable':
                data_to_write = quopri_decodestring(payload_data)

            elif data_encoding == 'base64':
                data_to_write = b64decode(payload_data)

            elif data_encoding == '7bit' or data_encoding == '8bit':
                # Need to get charset and decode with that too.
                charset = str(mimepart.get_charset())
                if charset == 'None': charset = None  # bug
                try:
                    assert charset
                    payload_data = encoding.attempt_decoding(charset, payload_data)
                except Exception, e:
                    detected_charset = detect_charset(payload_data)
                    detected_charset_encoding = detected_charset['encoding']
                    log.error("%s Failed decoding with %s. Now trying %s" % (e, charset , detected_charset_encoding))
                    try:
                        payload_data = encoding.attempt_decoding(detected_charset_encoding, payload_data)
                    except Exception, e:
                        log.error("That failed too. Hmph. Not sure how to recover here")
                        raise e
                    log.info("Success!")
                data_to_write = payload_data.encode('utf-8')
            else:
                raise Exception("Unknown encoding scheme:" + str(encoding))

            new_part.data_sha256 = sha256(data_to_write).hexdigest()
            new_part._data = data_to_write
            new_msg.parts.append(new_part)

    return new_messages, new_foldermeta

def safe_download(uids, folder, crispin_client):
    try:
        raw_messages = crispin_client.uids(uids)
        new_messages, new_foldermeta = process_messages(
                crispin_client.account, folder, raw_messages)
    except encoding.EncodingError, e:
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

class FolderSync(Greenlet):
    """ Per-folder sync engine. """
    def __init__(self, folder_name, account, crispin_client, log, shared_state):
        self.folder_name = folder_name
        self.account = account
        self.crispin_client = crispin_client
        self.log = log
        self.shared_state = shared_state
        self.state = None

        self.state_handlers = {
                'initial': self.initial_sync,
                'initial uid invalid': self.resync_uids,
                'poll': self.poll,
                'poll uid invalid': self.resync_uids,
                }

        Greenlet.__init__()

    def _run(self):
        try:
            syncmeta = db_session.query(SyncMeta).filter_by(
                    imapaccount=self.account,
                    folder_name=self.folder_name).one()
        except NoResultFound:
            syncmeta = SyncMeta(imapaccount=self.account,
                    folder_name=self.folder_name)
            db_session.add(syncmeta)
            db_session.commit()
        # NOTE: The parent MailSync handler could kill us at any time if it
        # receives a shutdown command. The shutdown command is equivalent
        # to ctrl-c.
        while True:
            self.state = syncmeta.state = self.state_handlers[syncmeta.state]()
            # The session should automatically mark this as dirty, but make sure.
            db_session.add(syncmeta)
            # State handlers are idempotent, so it's okay if we're killed
            # between the end of the handler and the commit.
            db_session.commit()

    def resync_uids(self):
        """ Call this when UIDVALIDITY is invalid to fix up the database.

        What happens here is we fetch new UIDs from the IMAP server and match
        them with X-GM-MSGIDs and sub in the new UIDs for the old. No messages
        are re-downloaded.
        """
        log.info("UIDVALIDITY for {0} has changed; resyncing UIDs".format(
            self.folder_name))
        raise Exception("Unimplemented")

    def initial_sync(self):
        """ Downloads entire messages and:
        1. sync folder => create TM, MM, BM
        2. expand threads => TM -> MM MM MM
        3. get related messages (can query IMAP for messages mapping thrids)

        For All Mail (Gmail-specific), we can skip the last step.
        For non-Gmail backends, we can skip #2, since we have no way to
        deduplicate threads server-side.
        """
        self.log.info('Starting initial sync for {0}'.format(self.folder_name))

        local_uids = self.account.all_uids(self.folder_name)
        self.crispin_client.select_folder(self.folder_name)

        remote_g_msgids = None
        cached_validity = fetch_uidvalidity(self.account, self.folder_name)
        if cached_validity is not None:
            if not uidvalidity_valid(self.crispin_client,
                    cached_validity.uid_validity):
                # bail bail bail
                return 'initial uidinvalid'
            # we can only do this if we have a cached validity; if there's
            # no cached validity it generally means we haven't previously run
            remote_g_msgids = self._retrieve_g_msgid_cache(local_uids,
                    cached_validity)

        if remote_g_msgids is None:
            remote_g_msgids = self.crispin_client.g_msgids()
            set_cache("_".join([self.account.email_address, self.folder_name,
                "remote_g_msgids"]), remote_g_msgids)
            # make sure uidvalidity is up-to-date
            if cached_validity is None:
                db_session.add(UIDValidity(
                    account=self.account, folder_name=self.folder_name,
                    uid_validity=self.crispin_client.selected_uidvalidity,
                    highestmodseq=self.crispin_client.selected_highestmodseq))
                db_session.commit()
            else:
                cached_validity.uid_validity = \
                        self.crispin_client.selected_uidvalidity
                cached_validity.highestmodseq = \
                        self.crispin_client.selected_highestmodseq
                db_session.add(cached_validity)
                db_session.commit()

        remote_uids = sorted(remote_g_msgids.keys(), key=int)
        self.log.info("Found {0} UIDs for folder {1}".format(
            len(remote_uids), self.folder_name))
        self.log.info("Already have {0} items".format(len(local_uids)))

        deleted_uids = set(local_uids).difference(set(remote_uids))
        unknown_uids = set(remote_uids).difference(set(local_uids))

        if deleted_uids:
            self.account.remove_messages(deleted_uids, self.folder_name)
            self.log.info("Removed the following UIDs that no longer exist on the server: {0}".format(' '.join([str(u) for u in sorted(deleted_uids, key=int)])))

        # deduplicate message download using X-GM-MSGID
        local_g_msgids = self.account.all_g_msgids()
        full_download, foldermeta_only = partition(
                lambda uid: remote_g_msgids[uid] in local_g_msgids,
                sorted(unknown_uids))

        self.log.info("{0} uids left to fetch".format(len(full_download)))

        self.log.info("Skipping {0} uids downloaded via other folders".format(
            len(foldermeta_only)))
        if len(foldermeta_only) > 0:
            self._add_new_foldermeta(remote_g_msgids, foldermeta_only)

        self.log.info("Starting sync for {0} with chunks of size {1}".format(
            self.folder_name, self.crispin_client.CHUNK_SIZE))
        # we prioritize message download by reverse-UID order, which generally
        # puts more recent messages first
        for uids in chunk(reversed(full_download), self.crispin_client.CHUNK_SIZE):
            self._download_new_messages(uids, len(local_uids), len(remote_uids))

        # complete X-GM-MSGID mapping is no longer needed after initial sync
        rm_cache("_".join([self.account.email_address, self.folder_name,
            "remote_g_msgids"]))
        # XXX TODO: check for consistency with datastore here before committing
        # state: download any missing messages, delete any messages that we
        # have that the server doesn't. that way, worst case if sync engine
        # bugs trickle through is we lose some flags.
        self.log.info("Saved all messages and metadata on {0} to UIDVALIDITY {1} / HIGHESTMODSEQ {2}".format(self.folder_name, self.crispin_client.selected_uidvalidity, self.crispin_client.selected_highestmodseq))

        self.log.info("Finished.")

    def _download_new_messages(self, uids, num_local_messages, num_remote_messages):
        new_messages, new_foldermeta = safe_download(
                uids, self.folder_name, self.crispin_client)
        db_session.add_all(new_foldermeta)
        db_session.add_all(new_messages)
        # Save message part blobs before committing changes to db.
        for msg in new_messages:
            threads = [Greenlet.spawn(part.save, part._data) \
                    for part in msg.parts]
            # Fatally abort if part saves error out. Messages in this
            # chunk will be retried when the sync is restarted.
            g_check_join(threads, "Could not save message parts to blob store!")

        # XXX clear data on part objects to save memory?
        # garbge_collect()

        db_session.commit()

        num_local_messages += len(uids) + 0.0

        percent_done = (num_local_messages / num_remote_messages) * 100
        self.shared_state['status_callback'](self.account, 'initial',
                (self.folder_name, percent_done))
        self.log.info("Syncing %s -- %.4f%% (%i/%i)" % (
            self.folder_name, percent_done,
            num_local_messages, num_remote_messages))

    def _add_new_foldermeta(self, remote_g_msgids, uids):
        # collate messagemeta objects to relate the new foldersmeta objects to
        foldermeta_uid_for = dict([(g_msgid, uid) for (uid, g_msgid) \
                in remote_g_msgids.items() if uid in uids])
        foldermeta_g_msgids = [remote_g_msgids[uid] for uid in uids]
        messagemeta_for = dict([(foldermeta_uid_for[mm.g_msgid], mm) for \
                mm in db_session.query(MessageMeta).filter( \
                    MessageMeta.g_msgid.in_(foldermeta_g_msgids))])
        db_session.add_all(
                [FolderMeta(imapaccount_id=self.account.id,
                    folder_name=self.folder_name, msg_uid=uid, \
                    messagemeta=messagemeta_for[uid]) for uid in uids])
        db_session.commit()

    def _retrieve_g_msgid_cache(self, local_uids, cached_validity):
        self.log.info('Attempting to retrieve remote_g_msgids from cache')
        remote_g_msgids = get_cache("_".join(
            [self.account.email_address, self.folder_name, "remote_g_msgids"]))
        if remote_g_msgids is not None:
            self.log.info("Successfully retrieved remote_g_msgids cache")
            if self.crispin_client.selected_highestmodseq > \
                    cached_validity.highestmodseq:
                self._update_g_msgid_cache(remote_g_msgids, local_uids)
        else:
            self.log.info("No cached data found")
        return remote_g_msgids

    def _update_g_msgid_cache(self, remote_g_msgids, local_uids):
        """ If HIGHESTMODSEQ has changed since we saved the X-GM-MSGID cache,
            we need to query for any changes since then and update the saved
            data.
        """
        self.log.info("Updating cache with latest changes")
        # any uids we don't already have will be downloaded correctly
        # as usual, but updated uids need to be updated manually
        # XXX it may actually be faster to just query for X-GM-MSGID for the
        # whole folder rather than getting changed UIDs first; MODSEQ queries
        # are slow on large folders.
        modified = self.crispin_client.new_and_updated_uids(
                self.crispin_client.selected_highestmodseq)
        new, updated = new_or_updated(modified, self.folder_name,
                self.account.id, local_uids)
        self.log.info("{0} new and {1} updated UIDs".format(len(new), len(updated)))
        # for new, query g_msgids and update cache
        remote_g_msgids.update(self.crispin_client.g_msgids(new))
        set_cache("_".join([self.account.email_address, self.folder_name,
            "remote_g_msgids"]), remote_g_msgids)
        self.log.info("Updated cache with new messages")
        # for updated, it's easier to just update them now
        # bigger chunk because the data being fetched here is very small
        for uids in chunk(updated, 5*self.crispin_client.CHUNK_SIZE):
            self._update_metadata(uids)
        self.log.info("Updated metadata for modified messages")

    def _highestmodseq_update(self, folder, dummy, highestmodseq=None):
        if highestmodseq is None:
            highestmodseq = db_session.query(UIDValidity).filter_by(
                    account=self.account, folder_name=folder
                    ).one().highestmodseq
        uids = self.crispin_client.new_and_updated_uids(highestmodseq)
        log.info("Starting highestmodseq update on {0} (current HIGHESTMODSEQ: {1})".format(folder, self.crispin_client.selected_highestmodseq))
        if uids:
            new, updated = new_or_updated(uids, folder,
                    self.crispin_client.account.id)
            log.info("{0} new and {1} updated UIDs".format(len(new), len(updated)))
            for uids in chunk(new, self.crispin_client.CHUNK_SIZE):
                # XXX TODO: dedupe this code with _initial_sync
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
                    # Clear data stored on Block objects here. Hopefully this
                    # will help with memory issues.
                    for part in msg['parts']:
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
        self._update_cached_highestmodseq(folder)
        db_session.commit()

    def _update_cached_highestmodseq(self, folder, cached_validity=None):
        if cached_validity is None:
            cached_validity = db_session.query(UIDValidity).filter_by(
                    account_id=self.crispin_client.account.id,
                    folder_name=folder).one()
        cached_validity.highestmodseq = self.crispin_client.selected_highestmodseq
        db_session.add(cached_validity)

    def poll(self):
        """ Poll this every N seconds for active (logged-in) users and every
            N minutes for logged-out users. It checks for changed message metadata
            and new messages using CONDSTORE / HIGHESTMODSEQ and also checks for
            deleted messages.

            We may also wish to frob update frequencies based on which folder
            a user has visible in the UI as well.
        """
        self.log.info("polling {0} folder {1}".format(
            self.account.email_address, self.folder_name))
        cached_validity = fetch_uidvalidity(self.account, self.folder_name)
        # we use status instead of select here because it's way faster and
        # we're not sure we want to commit to a session yet
        status = self.crispin_client.folder_status(self.folder_name)
        if status['HIGHESTMODSEQ'] > cached_validity.highestmodseq:
            self.crispin_client.select_folder(self.folder_name)
            if not uidvalidity_valid(self.crispin_client, cached_validity):
                return 'poll uidinvalid'
            self._highestmodseq_update(self.folder_name,
                    cached_validity.highestmodseq)

        self.shared_state['status_callback'](
            self.account, 'poll', datetime.utcnow().isoformat())
        sleep(self.n)

    def _remove_deleted_messages(self):
        """ Works as follows:
            1. do a LIST on the current folder to see what messages are on the server
            2. compare to message uids stored locally
            3. purge messages we have locally but not on the server. ignore
                messages we have on the server that aren't local.
        """
        remote_uids = self.crispin_client.all_uids()
        local_uids = [uid for uid, in
                db_session.query(FolderMeta.msg_uid).filter_by(
                    folder_name=self.crispin_client.selected_folder_name,
                    imapaccount_id=self.crispin_client.account.id)]
        if len(remote_uids) > 0 and len(local_uids) > 0:
            assert type(remote_uids[0]) != type('')

        to_delete = set(local_uids).difference(set(remote_uids))
        if to_delete:
            self.account.delete_messages(to_delete,
                    self.crispin_client.selected_folder_name)
            self.log.info("Deleted {0} removed messages".format(len(to_delete)))

    def _update_metadata(self, uids):
        """ Update flags (the only metadata that can change). """
        new_flags = self.crispin_client.flags(uids)
        assert sorted(uids, key=int) == sorted(new_flags.keys, key=int), \
                "server uids != local uids"
        self.log.info("new flags: {0}".format(new_flags))
        self.account.update_metadata(self.crispin_client.selected_folder_name,
                uids, new_flags)


class MailSync(Greenlet):
    """ Top-level controller for an account's mail sync. Spawns individual
        FolderSync greenlets for each folder.

        poll_frequency and heartbeat are in seconds.
    """
    def __init__(self, account, status_callback, poll_frequency=5, heartbeat=1):
        self.inbox = Queue()
        # how often to check inbox
        self.heartbeat = heartbeat

        self.crispin_client = refresh_crispin(account.email_address)
        self.account = account
        self.log = configure_sync_logging(account)

        # stuff that might be updated later and we want to keep a shared
        # reference on child greenlets (per-folder sync engines)
        self.shared_state = {
                'poll_frequency': poll_frequency,
                'status_callback': status_callback }

        Greenlet.__init__(self)

    def _run(self):
        sync = Greenlet.spawn(self.sync)
        while not sync.ready():
            try:
                cmd = self.inbox.get_nowait()
                if not self.process_command(cmd):
                    self.log.info("Stopping sync for {0}".format(
                        self.account.email_address))
                    # ctrl-c, basically!
                    kill(sync)
                    return
            except Empty:
                sleep(self.heartbeat)
        assert not sync.successful(), "mail sync should run forever!"
        raise sync.exception

    def process_command(self, cmd):
        """ Returns True if successful, or False if process should abort. """
        self.log.info("processing command {0}".format(cmd))
        return cmd != 'shutdown'

    def sync(self):
        """ Start per-folder syncs. Only have one per-folder sync in the
            'initial' state at a time.
        """
        for folder in self.crispin_client.sync_folders:
            thread = FolderSync(folder, self.account,
                    self.crispin_client, self.log, self.shared_state)
            thread.start()
            while not thread.state.startswith('poll'):
                sleep(self.heartbeat)

        # Just hang out. We don't want to block, but we don't want to return
        # either, since that will let the threads go out of scope.
        while True:
            sleep(self.heartbeat)

### misc

def notify(account, mtype, message):
    """ Pass a message on to the notification dispatcher which deals with
        pubsub stuff for connected clients.
    """
    pass
    # self.log.info("message from {0}: [{1}] {2}".format(
    # account.email_address, mtype, message))

### zerorpc

class SyncService:
    """ ZeroRPC interface to syncing. """
    def __init__(self):
        # { account_id: MailSync() }
        self.monitors = dict()
        # READ ONLY from API calls, writes happen from callbacks from monitor
        # greenlets.
        # { 'account_id': { 'state': 'initial sync', 'status': '0'} }
        # 'state' can be ['initial sync', 'poll']
        # 'status' is the percent-done for initial sync, polling start time otherwise
        # all data in here ought to be msgpack-serializable!
        self.statuses = dict()

        # Restart existing active syncs.
        # (Later we will want to partition these across different machines!)
        for email_address, in db_session.query(IMAPAccount.email_address).filter_by(
                sync_active=True):
            self.start_sync(email_address)

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
                results[account.email_address] = \
                        'Account {0} is syncing on host {1}'.format(
                            account.email_address, account.sync_host)
            elif account.id not in self.monitors:
                try:
                    account.sync_lock()
                    def update_status(account, state, status):
                        """ I really really wish I were a lambda """
                        self.statuses[account.id] = dict(
                                state=state, status=status)
                        notify(account, state, status)

                    monitor = MailSync(account, update_status)
                    self.monitors[account.id] = monitor
                    monitor.start()
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
