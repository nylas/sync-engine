""" IMAPClient wrapper for the Nilas Sync Engine. """
import contextlib
import re
import time
import imaplib
import imapclient

# Even though RFC 2060 says that the date component must have two characters
# (either two digits or space+digit), it seems that some IMAP servers only
# return one digit. Fun times.
imaplib.InternalDate = re.compile(
    r'.*INTERNALDATE "'
    r'(?P<day>[ 0123]?[0-9])-'   # insert that `?` to make first digit optional
    r'(?P<mon>[A-Z][a-z][a-z])-'
    r'(?P<year>[0-9][0-9][0-9][0-9])'
    r' (?P<hour>[0-9][0-9]):'
    r'(?P<min>[0-9][0-9]):'
    r'(?P<sec>[0-9][0-9])'
    r' (?P<zonen>[-+])(?P<zoneh>[0-9][0-9])(?P<zonem>[0-9][0-9])'
    r'"')

import functools
import threading
from email.parser import HeaderParser

from collections import namedtuple, defaultdict

import gevent
from gevent import socket
from gevent.lock import BoundedSemaphore
from gevent.queue import Queue

from inbox.util.concurrency import retry
from inbox.util.itert import chunk
from inbox.util.misc import or_none, timed
from inbox.basicauth import ValidationError, GmailSettingError
from inbox.models.session import session_scope
from inbox.models.account import Account
from inbox.log import get_logger
log = get_logger()

__all__ = ['CrispinClient', 'GmailCrispinClient', 'CondStoreCrispinClient']

# Unify flags API across IMAP and Gmail
Flags = namedtuple('Flags', 'flags')
# Flags includes labels on Gmail because Gmail doesn't use \Draft.
GmailFlags = namedtuple('GmailFlags', 'flags labels')
GMetadata = namedtuple('GMetadata', 'msgid thrid')
RawMessage = namedtuple(
    'RawImapMessage',
    'uid internaldate flags body g_thrid g_msgid g_labels')
RawFolder = namedtuple('RawFolder', 'display_name role')

# Lazily-initialized map of account ids to lock objects.
# This prevents multiple greenlets from concurrently creating duplicate
# connection pools for a given account.
_lock_map = defaultdict(threading.Lock)


CONN_DISCARD_EXC_CLASSES = (socket.error, imaplib.IMAP4.error)


class FolderMissingError(Exception):
    pass


def _get_connection_pool(account_id, pool_size, pool_map, readonly):
    with _lock_map[account_id]:
        if account_id not in pool_map:
            pool_map[account_id] = CrispinConnectionPool(
                account_id, num_connections=pool_size, readonly=readonly)
        return pool_map[account_id]


def connection_pool(account_id, pool_size=3, pool_map=dict()):
    """ Per-account crispin connection pool.

    Use like this:

        with crispin.connection_pool(account_id).get() as crispin_client:
            # your code here
            pass

    Note that the returned CrispinClient could have ANY folder selected, or
    none at all! It's up to the calling code to handle folder sessions
    properly. We don't reset to a certain select state because it's slow.
    """
    return _get_connection_pool(account_id, pool_size, pool_map, True)


def writable_connection_pool(account_id, pool_size=1, pool_map=dict()):
    """ Per-account crispin connection pool, with *read-write* connections.

    Use like this:

        conn_pool = crispin.writable_connection_pool(account_id)
        with conn_pool.get() as crispin_client:
            # your code here
            pass
    """
    return _get_connection_pool(account_id, pool_size, pool_map, False)


class CrispinConnectionPool(object):
    """
    Connection pool for Crispin clients.

    Connections in a pool are specific to an IMAPAccount.

    Parameters
    ----------
    account_id : int
        Which IMAPAccount to open up a connection to.
    num_connections : int
        How many connections in the pool.
    readonly : bool
        Is the connection to the IMAP server read-only?
    """
    def __init__(self, account_id, num_connections, readonly):
        log.info('Creating Crispin connection pool for account {} with {} '
                 'connections'.format(account_id, num_connections))
        self.account_id = account_id
        self.readonly = readonly
        self._queue = Queue(num_connections, items=num_connections * [None])
        self._sem = BoundedSemaphore(num_connections)
        self._set_account_info()

    @contextlib.contextmanager
    def get(self):
        """ Get a connection from the pool, or instantiate a new one if needed.
        If `num_connections` connections are already in use, block until one is
        available.
        """
        # A gevent semaphore is granted in the order that greenlets tried to
        # acquire it, so we use a semaphore here to prevent potential
        # starvation of greenlets if there is high contention for the pool.
        # The queue implementation does not have that property; having
        # greenlets simply block on self._queue.get(block=True) could cause
        # individual greenlets to block for arbitrarily long.
        self._sem.acquire()
        client = self._queue.get()
        try:
            if client is None:
                client = self._new_connection()
            yield client
        except CONN_DISCARD_EXC_CLASSES as exc:
            # Discard the connection on socket or IMAP errors. Technically this
            # isn't always necessary, since if you got e.g. a FETCH failure you
            # could reuse the same connection. But for now it's the simplest
            # thing to do.
            log.info('IMAP connection error; discarding connection',
                     exc_info=True)
            if client is not None:
                try:
                    client.logout()
                except:
                    log.error('Error on IMAP logout', exc_info=True)
                client = None
            raise exc
        except:
            raise
        finally:
            self._queue.put(client)
            self._sem.release()

    def _set_account_info(self):
        with session_scope() as db_session:
            account = db_session.query(Account).get(self.account_id)
            self.sync_state = account.sync_state
            self.provider_info = account.provider_info
            self.email_address = account.email_address
            self.auth_handler = account.auth_handler
            if account.provider == 'gmail':
                self.client_cls = GmailCrispinClient
            elif (getattr(account, 'supports_condstore', None) or
                  account.provider_info.get('condstore')):
                self.client_cls = CondStoreCrispinClient
            else:
                self.client_cls = CrispinClient

    def _new_connection(self):
        try:
            with session_scope() as db_session:
                account = db_session.query(Account).get(self.account_id)
                conn = self.auth_handler.connect_account(account)
                # If we can connect the account, then we can set the state
                # to 'running' if it wasn't already
                if self.sync_state != 'running':
                    self.sync_state = account.sync_state = 'running'
            return self.client_cls(self.account_id, self.provider_info,
                                   self.email_address, conn,
                                   readonly=self.readonly)
        except ValidationError, e:
            log.error('Error validating',
                      account_id=self.account_id,
                      logstash_tag='mark_invalid')
            with session_scope() as db_session:
                account = db_session.query(Account).get(self.account_id)
                account.mark_invalid()
                account.update_sync_error(str(e))
            raise


def _exc_callback():
    log.info('Connection broken with error; retrying with new connection',
             exc_info=True)
    gevent.sleep(5)


def _fail_callback():
    log.error('Max retries reached. Aborting', exc_info=True)


retry_crispin = functools.partial(
    retry, retry_classes=CONN_DISCARD_EXC_CLASSES, exc_callback=_exc_callback,
    fail_callback=_fail_callback, max_count=10, reset_interval=150)


class CrispinClient(object):
    """
    Generic IMAP client wrapper.

    One thing to note about crispin clients is that *all* calls operate on
    the currently selected folder.

    Crispin will NEVER implicitly select a folder for you.

    This is very important! IMAP only guarantees that folder message UIDs
    are valid for a "session", which is defined as from the time you
    SELECT a folder until the connection is closed or another folder is
    selected.

    Crispin clients *always* return long ints rather than strings for number
    data types, such as message UIDs, Google message IDs, and Google thread
    IDs.

    All inputs are coerced to strings before being passed off to the IMAPClient
    connection.

    You should really be interfacing with this class via a connection pool,
    see `connection_pool()`.

    Parameters
    ----------
    account_id : int
        Database id of the associated IMAPAccount.
    conn : IMAPClient
        Open IMAP connection (should be already authed).
    readonly : bool
        Whether or not to open IMAP connections as readonly.

    """
    PROVIDER = 'IMAP'
    # NOTE: Be *careful* changing this! Downloading too much at once may
    # cause memory errors that only pop up in extreme edge cases.
    CHUNK_SIZE = 1

    def __init__(self, account_id, provider_info, email_address, conn,
                 readonly=True):
        self.account_id = account_id
        self.provider_info = provider_info
        self.email_address = email_address
        # IMAP isn't stateless :(
        self.selected_folder = None
        self._folder_names = None
        self.conn = conn
        self.readonly = readonly

    def _fetch_folder_list(self):
        """ NOTE: XLIST is deprecated, so we just use LIST.

        An example response with some other flags:

            * LIST (\HasNoChildren) "/" "INBOX"
            * LIST (\Noselect \HasChildren) "/" "[Gmail]"
            * LIST (\HasNoChildren \All) "/" "[Gmail]/All Mail"
            * LIST (\HasNoChildren \Drafts) "/" "[Gmail]/Drafts"
            * LIST (\HasNoChildren \Important) "/" "[Gmail]/Important"
            * LIST (\HasNoChildren \Sent) "/" "[Gmail]/Sent Mail"
            * LIST (\HasNoChildren \Junk) "/" "[Gmail]/Spam"
            * LIST (\HasNoChildren \Flagged) "/" "[Gmail]/Starred"
            * LIST (\HasNoChildren \Trash) "/" "[Gmail]/Trash"

        IMAPClient parses this response into a list of
        (flags, delimiter, name) tuples.
        """
        return self.conn.list_folders()

    def select_folder(self, folder, uidvalidity_cb):
        """ Selects a given folder.

        Makes sure to set the 'selected_folder' attribute to a
        (folder_name, select_info) pair.

        Selecting a folder indicates the start of an IMAP session.  IMAP UIDs
        are only guaranteed valid for sessions, so the caller must provide a
        callback that checks UID validity.

        Starts a new session even if `folder` is already selected, since
        this does things like e.g. makes sure we're not getting
        cached/out-of-date values for HIGHESTMODSEQ from the IMAP server.
        """
        try:
            select_info = self.conn.select_folder(
                folder, readonly=self.readonly)
        except imapclient.IMAPClient.Error as e:
            # Specifically point out folders that come back as missing by
            # checking for Yahoo / Gmail / Outlook (Hotmail) specific errors:
            if '[NONEXISTENT] Unknown Mailbox:' in e.message or \
               'does not exist' in e.message or \
               "doesn't exist" in e.message:
                raise FolderMissingError(folder)
            # We can't assume that all errors here are caused by the folder
            # being deleted, as other connection errors could occur - but we
            # want to make sure we keep track of different providers'
            # "nonexistent" messages, so log this event.
            log.error("IMAPClient error selecting folder. May be deleted",
                           error=str(e))
            raise

        select_info['UIDVALIDITY'] = long(select_info['UIDVALIDITY'])
        self.selected_folder = (folder, select_info)
        # Don't propagate cached information from previous session
        self._folder_names = None
        return uidvalidity_cb(self.account_id, folder, select_info)

    @property
    def selected_folder_name(self):
        return or_none(self.selected_folder, lambda f: f[0])

    @property
    def selected_folder_info(self):
        return or_none(self.selected_folder, lambda f: f[1])

    @property
    def selected_uidvalidity(self):
        return or_none(self.selected_folder_info, lambda i: i['UIDVALIDITY'])

    def sync_folders(self):
        """
        List of folders to sync.

        In generic IMAP, the 'INBOX' folder is required.

        Returns
        -------
        list
            Folders to sync (as strings).

        """
        to_sync = []
        have_folders = self.folder_names()

        assert 'inbox' in have_folders, \
            "Missing required 'inbox' folder for account_id: {}".\
            format(self.account_id)

        for names in have_folders.itervalues():
            to_sync.extend(names)

        return to_sync

    def folder_names(self, force_resync=False):
        """
        Return the folder names for the account as a mapping from
        recognized role: list of folder names,
        for example: 'sent': ['Sent Items', 'Sent'].

        The list of recognized folder roles is in:
        inbox/models/constants.py

        Folders that do not belong to a recognized role are mapped to
        None, for example: None: ['MyFolder', 'OtherFolder'].

        The mapping is also cached in self._folder_names

        Parameters:
        -----------
        force_resync: boolean
            Return the cached mapping or return a refreshed mapping
            (after refetching from the remote).

        """
        if force_resync or self._folder_names is None:
            self._folder_names = defaultdict(list)

            raw_folders = self.folders()
            for f in raw_folders:
                self._folder_names[f.role].append(f.display_name)

        return self._folder_names

    def folders(self):
        """
        Fetch the list of folders for the account from the remote, return as a
        list of RawFolder objects.

        NOTE:
        Always fetches the list of folders from the remote.

        """
        raw_folders = []

        folders = self._fetch_folder_list()
        for flags, delimiter, name in folders:
            if u'\\Noselect' in flags or u'\\NoSelect' in flags \
                    or u'\\NonExistent' in flags:
                # Special folders that can't contain messages
                continue

            raw_folder = self._process_folder(name, flags)
            raw_folders.append(raw_folder)

        return raw_folders

    def _process_folder(self, display_name, flags):
        """
        Determine the role for the remote folder from its `name` and `flags`.

        Returns
        -------
            RawFolder representing the folder

        """
        # TODO[[k]: Important/ Starred for generic IMAP?

        # Different providers have different names for folders, here
        # we have a default map for common name mapping, additional
        # mappings can be provided via the provider configuration file
        default_folder_map = {
            'inbox': 'inbox',
            'drafts': 'drafts',
            'draft': 'drafts',
            'junk': 'spam',
            'spam': 'spam',
            'archive': 'archive',
            'sent': 'sent',
            'trash': 'trash'}

        # Additionally we provide a custom mapping for providers that
        # don't fit into the defaults.
        folder_map = self.provider_info.get('folder_map', {})

        # Some providers also provide flags to determine common folders
        # Here we read these flags and apply the mapping
        flag_map = {'\\Trash': 'trash', '\\Sent': 'sent', '\\Drafts': 'drafts',
                    '\\Junk': 'spam', '\\Inbox': 'inbox', '\\Spam': 'spam'}

        role = default_folder_map.get(display_name.lower())

        if not role:
            role = folder_map.get(display_name)

        if not role:
            for flag in flags:
                role = flag_map.get(flag)

        return RawFolder(display_name=display_name, role=role)

    def folder_status(self, folder):
        status = [long(val) for val in self.conn.folder_status(
            folder, ('UIDVALIDITY'))]

        return status

    def create_folder(self, name):
        self.conn.create_folder(name)

    def search_uids(self, criteria):
        """
        Find not-deleted UIDs in this folder matching the criteria.

        See http://tools.ietf.org/html/rfc3501.html#section-6.4.4 for valid
        criteria.

        """
        full_criteria = ['UNDELETED']
        if isinstance(criteria, list):
            full_criteria.extend(criteria)
        else:
            full_criteria.append(criteria)
        return sorted([long(uid) for uid in self.conn.search(full_criteria)])

    def all_uids(self):
        """ Fetch all UIDs associated with the currently selected folder.

        Returns
        -------
        list
            UIDs as integers sorted in ascending order.
        """
        # Note that this list may include items which have been marked for
        # deletion with the \Deleted flag, but not yet actually removed via
        # an EXPUNGE command. I choose to include them here since most clients
        # will still display them (sometimes with a strikethrough). If showing
        # these is a problem, we can either switch back to searching for
        # 'UNDELETED' or doing a fetch for ['UID', 'FLAGS'] and filtering.

        try:
            t = time.time()
            fetch_result = self.conn.search(['ALL'])
        except imaplib.IMAP4.error as e:
            if e.message.find('UID SEARCH wrong arguments passed') >= 0:
                # Mail2World servers fail for the otherwise valid command
                # 'UID SEARCH ALL' but strangely pass for 'UID SEARCH ALL UID'
                log.debug("Getting UIDs failed when using 'UID SEARCH "
                          "ALL'. Switching to alternative 'UID SEARCH "
                          "ALL UID", exception=e)
                t = time.time()
                fetch_result = self.conn.search(['ALL', 'UID'])
            else:
                raise

        elapsed = time.time() - t
        log.debug('Requested all UIDs',
                   selected_folder=self.selected_folder_name,
                   search_time=elapsed,
                   total_uids=len(fetch_result))
        return sorted([long(uid) for uid in fetch_result])

    def uids(self, uids):
        uid_set = set(uids)
        messages = []
        raw_messages = {}

        for uid in uid_set:
            try:
                raw_messages.update(self.conn.fetch(
                    uid, ['BODY.PEEK[] INTERNALDATE FLAGS']))
            except imapclient.IMAPClient.Error as e:
                if ('[UNAVAILABLE] UID FETCH Server error '
                        'while fetching messages') in str(e):
                    log.info('Got an exception while requesting an UID',
                             uid=uid, error=e,
                             logstash_tag='imap_download_exception')
                    continue
                else:
                    log.info(('Got an unhandled exception while '
                              'requesting an UID'),
                             uid=uid, error=e,
                             logstash_tag='imap_download_exception')
                    raise

        for uid in sorted(raw_messages.iterkeys(), key=long):
            # Skip handling unsolicited FETCH responses
            if uid not in uid_set:
                continue
            msg = raw_messages[uid]
            if msg.keys() == ['SEQ']:
                log.error('No data returned for UID, skipping', uid=uid)
                continue

            messages.append(RawMessage(uid=long(uid),
                                       internaldate=msg['INTERNALDATE'],
                                       flags=msg['FLAGS'],
                                       body=msg['BODY[]'],
                                       # TODO: use data structure that isn't
                                       # Gmail-specific
                                       g_thrid=None, g_msgid=None,
                                       g_labels=None))
        return messages

    def flags(self, uids):
        data = self.conn.fetch(uids, ['FLAGS'])
        uid_set = set(uids)
        return {uid: Flags(ret['FLAGS'])
                for uid, ret in data.items() if uid in uid_set}

    def delete_uids(self, uids):
        uids = [str(u) for u in uids]
        self.conn.delete_messages(uids)
        self.conn.expunge()

    def set_starred(self, uids, starred):
        if starred:
            self.conn.add_flags(uids, ['\\Flagged'])
        else:
            self.conn.remove_flags(uids, ['\\Flagged'])

    def set_unread(self, uids, unread):
        uids = [str(u) for u in uids]
        if unread:
            self.conn.remove_flags(uids, ['\\Seen'])
        else:
            self.conn.add_flags(uids, ['\\Seen'])

    def save_draft(self, message, date=None):
        assert self.selected_folder_name in self.folder_names()['drafts'], \
            'Must select a drafts folder first ({0})'.\
            format(self.selected_folder_name)

        self.conn.append(self.selected_folder_name, message, ['\\Draft',
                                                              '\\Seen'], date)

    def create_message(self, message, date=None):
        """
        Create a message on the server. Only used to fix server-side bugs,
        like iCloud not saving Sent messages.

        """
        assert self.selected_folder_name in self.folder_names()['sent'], \
            'Must select sent folder first ({0})'.\
            format(self.selected_folder_name)

        self.conn.append(self.selected_folder_name, message, [], date)

    def fetch_headers(self, uids):
        """
        Fetch headers for the given uids. Chunked because certain providers
        fail with 'Command line too large' if you feed them too many uids at
        once.

        """
        headers = {}
        for uid_chunk in chunk(uids, 100):
            headers.update(self.conn.fetch(
                uid_chunk, ['BODY.PEEK[HEADER]']))
        return headers

    def find_by_header(self, header_name, header_value):
        """Find all uids in the selected folder with the given header value."""
        all_uids = self.all_uids()
        # It would be nice to just search by header too, but some backends
        # don't support that, at least not if you want to search by X-INBOX-ID
        # header. So fetch the header for each draft and see if we
        # can find one that matches.
        # TODO(emfree): are there other ways we can narrow the result set a
        # priori (by subject or date, etc.)
        matching_draft_headers = self.fetch_headers(all_uids)
        results = []
        for uid, response in matching_draft_headers.iteritems():
            headers = response['BODY[HEADER]']
            parser = HeaderParser()
            header = parser.parsestr(headers).get(header_name)
            if header == header_value:
                results.append(uid)

        return results

    def delete_draft(self, inbox_uid, message_id_header):
        """
        Delete a draft, as identified either by its X-Inbox-Id or by its
        Message-Id header. We first delete the message from the Drafts folder,
        and then also delete it from the Trash folder if necessary.

        """
        drafts_folder_name = self.folder_names()['drafts'][0]
        self.conn.select_folder(drafts_folder_name)
        self._delete_message(inbox_uid, message_id_header)

        trash_folder_name = self.folder_names()['trash'][0]
        self.conn.select_folder(trash_folder_name)
        self._delete_message(inbox_uid, message_id_header)

    def _delete_message(self, inbox_uid, message_id_header):
        """
        Delete a message from the selected folder, using either the X-Inbox-Id
        header or the Message-Id header to locate it. Does nothing if no
        matching messages are found, or if more than one matching message is
        found.

        """
        assert inbox_uid or message_id_header, 'Need at least one header'
        if inbox_uid:
            matching_uids = self.find_by_header('X-Inbox-Id', inbox_uid)
        else:
            matching_uids = self.find_by_header('Message-Id',
                                                message_id_header)
        if not matching_uids:
            log.error('No remote messages found to delete',
                      inbox_uid=inbox_uid,
                      message_id_header=message_id_header)
            return
        if len(matching_uids) > 1:
            log.error('Multiple remote messages found to delete',
                      inbox_uid=inbox_uid,
                      message_id_header=message_id_header,
                      uids=matching_uids)
            return
        self.conn.delete_messages(matching_uids)
        self.conn.expunge()

    def logout(self):
        self.conn.logout()


class CondStoreCrispinClient(CrispinClient):
    def select_folder(self, folder, uidvalidity_cb):
        ret = super(CondStoreCrispinClient,
                    self).select_folder(folder, uidvalidity_cb)
        # We need to issue a STATUS command asking for HIGHESTMODSEQ
        # because some servers won't enable CONDSTORE support otherwise
        status = self.folder_status(folder)
        if 'HIGHESTMODSEQ' in self.selected_folder_info:
            self.selected_folder_info['HIGHESTMODSEQ'] = \
                long(self.selected_folder_info['HIGHESTMODSEQ'])
        elif 'HIGHESTMODSEQ' in status:
            self.selected_folder_info['HIGHESTMODSEQ'] = \
                status['HIGHESTMODSEQ']
        return ret

    def folder_status(self, folder):
        status = self.conn.folder_status(
            folder, ('UIDVALIDITY', 'HIGHESTMODSEQ', 'UIDNEXT'))
        for param in status:
            status[param] = long(status[param])

        return status

    def idle(self, timeout):
        """Idle for up to `timeout` seconds. Make sure we take the connection
        back out of idle mode so that we can reuse this connection in another
        context."""
        self.conn.idle()
        try:
            r = self.conn.idle_check(timeout)
        except:
            self.conn.idle_done()
            raise
        self.conn.idle_done()
        return r

    @property
    def selected_highestmodseq(self):
        return or_none(self.selected_folder_info, lambda i: i['HIGHESTMODSEQ'])

    @timed
    def new_and_updated_uids(self, modseq):
        resp = self.conn.fetch('1:*', ['FLAGS'],
                               modifiers=['CHANGEDSINCE {}'.format(modseq)])
        # TODO(emfree): It may be useful to hold on to the whole response here
        # and/or fetch more metadata, not just return the UIDs.
        return sorted(resp.keys())


class GmailCrispinClient(CondStoreCrispinClient):
    PROVIDER = 'gmail'

    def sync_folders(self):
        """
        Gmail-specific list of folders to sync.

        In Gmail, every message is in `All Mail`, with the exception of
        messages in the Trash and Spam folders. So we only sync the `All Mail`,
        Trash and Spam folders.

        Returns
        -------
        list
            Folders to sync (as strings).

        """
        present_folders = self.folder_names()

        if 'all' not in present_folders:
            raise GmailSettingError(
                "Account {} ({}) is missing the 'All Mail' folder. This is "
                "probably due to 'Show in IMAP' being disabled. "
                "Please enable at "
                "https://mail.google.com/mail/#settings/labels"
                .format(self.account_id, self.email_address))

        # If the account has Trash, Spam folders, sync those too.
        to_sync = []
        for folder in ['all', 'trash', 'spam']:
            if folder in present_folders:
                to_sync.append(present_folders[folder][0])
        return to_sync

    def flags(self, uids):
        """
        Gmail-specific flags.

        Returns
        -------
        dict
            Mapping of `uid` (str) : GmailFlags.

        """
        data = self.conn.fetch(uids, ['FLAGS X-GM-LABELS'])
        uid_set = set(uids)
        return {uid: GmailFlags(ret['FLAGS'], ret['X-GM-LABELS'])
                for uid, ret in data.items() if uid in uid_set}

    def g_msgids(self, uids):
        """
        X-GM-MSGIDs for the given UIDs.

        Returns
        -------
        dict
            Mapping of `uid` (long) : `g_msgid` (long)

        """
        data = self.conn.fetch(uids, ['X-GM-MSGID'])
        uid_set = set(uids)
        return {uid: ret['X-GM-MSGID']
                for uid, ret in data.items() if uid in uid_set}

    def folder_names(self, force_resync=False):
        """
        Return the folder names ( == label names for Gmail) for the account
        as a mapping from recognized role: list of folder names in the
        role, for example: 'sent': ['Sent Items', 'Sent'].

        The list of recognized categories is in:
        inbox/models/constants.py

        Folders that do not belong to a recognized role are mapped to None, for
        example: None: ['MyFolder', 'OtherFolder'].

        The mapping is also cached in self._folder_names

        Parameters:
        -----------
        force_resync: boolean
            Return the cached mapping or return a refreshed mapping
            (after refetching from the remote).

        """
        if force_resync or self._folder_names is None:
            self._folder_names = defaultdict(list)

            raw_folders = self.folders()
            for f in raw_folders:
                self._folder_names[f.role].append(f.display_name)

        return self._folder_names

    def folders(self):
        """
        Fetch the list of folders for the account from the remote, return as a
        list of RawFolder objects.

        NOTE:
        Always fetches the list of folders from the remote.

        """
        raw_folders = []

        folders = self._fetch_folder_list()
        for flags, delimiter, name in folders:
            if u'\\Noselect' in flags or u'\\NoSelect' in flags \
                    or u'\\NonExistent' in flags:
                # Special folders that can't contain messages, usually
                # just '[Gmail]'
                continue

            raw_folder = self._process_folder(name, flags)
            raw_folders.append(raw_folder)

        return raw_folders

    def _process_folder(self, display_name, flags):
        """
        Determine the canonical_name for the remote folder from its `name` and
        `flags`.

        Returns
        -------
            RawFolder representing the folder

        """
        flag_map = {'\\Drafts': 'drafts', '\\Important': 'important',
                    '\\Sent': 'sent', '\\Junk': 'spam', '\\Flagged': 'starred',
                    '\\Trash': 'trash'}

        role = None
        if '\\All' in flags:
            role = 'all'
        elif display_name.lower() == 'inbox':
            # Special-case the display name here. In Gmail, the inbox
            # folder shows up in the folder list as 'INBOX', and in sync as
            # the label '\\Inbox'. We're just always going to give it the
            # display name 'Inbox'.
            role = 'inbox'
            display_name = 'Inbox'
        else:
            for flag in flags:
                if flag in flag_map:
                    role = flag_map[flag]

        return RawFolder(display_name=display_name, role=role)

    def uids(self, uids):
        raw_messages = self.conn.fetch(uids, ['BODY.PEEK[] INTERNALDATE FLAGS',
                                              'X-GM-THRID', 'X-GM-MSGID',
                                              'X-GM-LABELS'])

        messages = []
        uid_set = set(uids)
        for uid in sorted(raw_messages.iterkeys(), key=long):
            # Skip handling unsolicited FETCH responses
            if uid not in uid_set:
                continue
            msg = raw_messages[uid]
            messages.append(RawMessage(uid=long(uid),
                                       internaldate=msg['INTERNALDATE'],
                                       flags=msg['FLAGS'],
                                       body=msg['BODY[]'],
                                       g_thrid=long(msg['X-GM-THRID']),
                                       g_msgid=long(msg['X-GM-MSGID']),
                                       g_labels=msg['X-GM-LABELS']))
        return messages

    def g_metadata(self, uids):
        """ Download Gmail MSGIDs and THRIDs for the given messages.

        NOTE: only UIDs are guaranteed to be unique to a folder, X-GM-MSGID
        and X-GM-THRID may not be.

        Parameters
        ----------
        uids : list
            UIDs to fetch data for. Must be from the selected folder.

        Returns
        -------
        dict
            uid: GMetadata(msgid, thrid)
        """
        log.debug('fetching X-GM-MSGID and X-GM-THRID',
                  uid_count=len(uids))
        # Super long sets of uids may fail with BAD ['Could not parse command']
        # In that case, just fetch metadata for /all/ uids.
        if len(uids) > 1e6:
            data = self.conn.fetch('1:*', ['X-GM-MSGID', 'X-GM-THRID'])
        else:
            data = self.conn.fetch(uids, ['X-GM-MSGID', 'X-GM-THRID'])
        uid_set = set(uids)
        return {uid: GMetadata(ret['X-GM-MSGID'], ret['X-GM-THRID'])
                for uid, ret in data.items() if uid in uid_set}

    def expand_thread(self, g_thrid):
        """ Find all message UIDs in this account with X-GM-THRID equal to
        g_thrid.

        Requires the "All Mail" folder to be selected.

        Returns
        -------
        list
            All Mail UIDs (as integers), sorted most-recent first.
        """
        assert self.selected_folder_name in self.folder_names()['all'], \
            'Must select All Mail first ({})'.\
            format(self.selected_folder_name)

        criterion = 'X-GM-THRID {}'.format(g_thrid)
        uids = [long(uid) for uid in self.conn.search(['UNDELETED',
                                                       criterion])]
        # UIDs ascend over time; return in order most-recent first
        return sorted(uids, reverse=True)

    def find_messages(self, g_thrid):
        """ Get UIDs for the [sub]set of messages belonging to the given thread
            that are in the current folder.
        """
        criteria = 'X-GM-THRID {}'.format(g_thrid)
        return sorted([long(uid) for uid in
                       self.conn.search(['UNDELETED', criteria])])

    def get_labels(self, g_thrid):
        uids = self.find_messages(g_thrid)
        labels = self.conn.get_gmail_labels(uids)

        # the complicated list comprehension below simply flattens the list
        unique_labels = set([item for sublist in labels.values()
                             for item in sublist])
        return list(unique_labels)

    def delete(self, g_thrid, folder_name):
        """
        Permanent delete i.e. remove the corresponding label and add the
        `Trash` flag. We currently only allow this for Drafts, all other
        non-All Mail deletes are archives.

        """
        uids = self.find_messages(g_thrid)

        if folder_name in self.folder_names()['drafts']:
            # Remove Gmail's `Draft` label
            self.conn.remove_gmail_labels(uids, ['\Draft'])

            # Move to Gmail's `Trash` folder
            self.conn.delete_messages(uids)
            self.conn.expunge()

            # Delete from `Trash`
            trash_folder_name = self.folder_names()['trash'][0]
            self.conn.select_folder(trash_folder_name)

            trash_uids = self.find_messages(g_thrid)
            self.conn.delete_messages(trash_uids)
            self.conn.expunge()

    def find_by_header(self, header_name, header_value):
        criteria = ['UNDELETED',
                    'HEADER {} {}'.format(header_name, header_value)]
        return self.conn.search(criteria)
