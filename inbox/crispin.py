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
from sqlalchemy.orm import joinedload

from inbox.util.concurrency import retry
from inbox.util.itert import chunk
from inbox.util.misc import or_none
from inbox.basicauth import GmailSettingError
from inbox.models.session import session_scope
from inbox.models.backends.imap import ImapAccount
from inbox.models.backends.generic import GenericAccount
from inbox.models.backends.gmail import GmailAccount
from nylas.logging import get_logger
log = get_logger()

__all__ = ['CrispinClient', 'GmailCrispinClient']

# Unify flags API across IMAP and Gmail
Flags = namedtuple('Flags', 'flags')
# Flags includes labels on Gmail because Gmail doesn't use \Draft.
GmailFlags = namedtuple('GmailFlags', 'flags labels')
GMetadata = namedtuple('GMetadata', 'g_msgid g_thrid size')
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
                account_id, num_connections=pool_size,
                readonly=readonly)
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
            if (client is not None and not
                    isinstance(exc, (imaplib.IMAP4.abort, socket.error))):
                try:
                    client.logout()
                except Exception:
                    log.info('Error on IMAP logout', exc_info=True)
            client = None
            raise exc
        except:
            raise
        finally:
            self._queue.put(client)
            self._sem.release()

    def _set_account_info(self):
        with session_scope(self.account_id) as db_session:
            account = db_session.query(ImapAccount).get(self.account_id)
            self.sync_state = account.sync_state
            self.provider = account.provider
            self.provider_info = account.provider_info
            self.email_address = account.email_address
            self.auth_handler = account.auth_handler
            if account.provider == 'gmail':
                self.client_cls = GmailCrispinClient
            else:
                self.client_cls = CrispinClient

    def _new_raw_connection(self):
        """Returns a new, authenticated IMAPClient instance for the account."""
        with session_scope(self.account_id) as db_session:
            if self.provider == 'gmail':
                account = db_session.query(GmailAccount).options(
                    joinedload(GmailAccount.auth_credentials)).get(
                    self.account_id)
            else:
                account = db_session.query(GenericAccount).options(
                    joinedload(GenericAccount.secret)).get(self.account_id)
            db_session.expunge(account)

        return self.auth_handler.connect_account(account)

    def _new_connection(self):
        conn = self._new_raw_connection()
        return self.client_cls(self.account_id, self.provider_info,
                               self.email_address, conn,
                               readonly=self.readonly)


def _exc_callback():
    log.info('Connection broken with error; retrying with new connection',
             exc_info=True)
    gevent.sleep(5)


retry_crispin = functools.partial(
    retry, retry_classes=CONN_DISCARD_EXC_CLASSES, exc_callback=_exc_callback)


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

    @property
    def selected_uidnext(self):
        return or_none(self.selected_folder_info, lambda i: i.get('UIDNEXT'))

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

    def create_folder(self, name):
        self.conn.create_folder(name)

    def condstore_supported(self):
        # Technically QRESYNC implies CONDSTORE, although this is unlikely to
        # matter in practice.
        capabilities = self.conn.capabilities()
        return 'CONDSTORE' in capabilities or 'QRESYNC' in capabilities

    def idle_supported(self):
        return 'IDLE' in self.conn.capabilities()

    def search_uids(self, criteria):
        """
        Find UIDs in this folder matching the criteria. See
        http://tools.ietf.org/html/rfc3501.html#section-6.4.4 for valid
        criteria.

        """
        return sorted([long(uid) for uid in self.conn.search(criteria)])

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
                    uid, ['BODY.PEEK[]', 'INTERNALDATE', 'FLAGS']))
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
        if len(uids) > 100:
            # Some backends abort the connection if you give them a really
            # long sequence set of individual UIDs, so instead fetch flags for
            # all UIDs greater than or equal to min(uids).
            seqset = '{}:*'.format(min(uids))
        else:
            seqset = uids
        data = self.conn.fetch(seqset, ['FLAGS'])
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

        return self.conn.append(self.selected_folder_name, message, [], date)

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

    def delete_draft(self, message_id_header):
        """
        Delete a draft, as identified by its Message-Id header. We first delete
        the message from the Drafts folder,
        and then also delete it from the Trash folder if necessary.

        """
        log.info('Trying to delete draft', message_id_header=message_id_header)
        drafts_folder_name = self.folder_names()['drafts'][0]
        self.conn.select_folder(drafts_folder_name)
        draft_deleted = self._delete_message(message_id_header)
        if draft_deleted:
            trash_folder_name = self.folder_names()['trash'][0]
            self.conn.select_folder(trash_folder_name)
            self._delete_message(message_id_header)
        return draft_deleted

    def _delete_message(self, message_id_header):
        """
        Delete a message from the selected folder, using the Message-Id header
        to locate it. Does nothing if no matching messages are found, or if
        more than one matching message is found.

        """
        matching_uids = self.find_by_header('Message-Id', message_id_header)
        if not matching_uids:
            log.error('No remote messages found to delete',
                      message_id_header=message_id_header)
            return False
        if len(matching_uids) > 1:
            log.error('Multiple remote messages found to delete',
                      message_id_header=message_id_header,
                      uids=matching_uids)
            return False
        self.conn.delete_messages(matching_uids)
        self.conn.expunge()
        return True

    def logout(self):
        self.conn.logout()

    def idle(self, timeout):
        """Idle for up to `timeout` seconds. Make sure we take the connection
        back out of idle mode so that we can reuse this connection in another
        context."""
        self.conn.idle()
        try:
            with self._restore_timeout():
                r = self.conn.idle_check(timeout)
        except:
            self.conn.idle_done()
            raise
        self.conn.idle_done()
        return r

    @contextlib.contextmanager
    def _restore_timeout(self):
        # IMAPClient.idle_check() calls setblocking(1) on the underlying
        # socket, erasing any previously set timeout. So make sure to restore
        # the timeout.
        sock = getattr(self.conn._imap, 'sslobj', self.conn._imap.sock)
        timeout = sock.gettimeout()
        try:
            yield
        finally:
            sock.settimeout(timeout)

    def condstore_changed_flags(self, modseq):
        data = self.conn.fetch('1:*', ['FLAGS'],
                               modifiers=['CHANGEDSINCE {}'.format(modseq)])
        return {uid: Flags(ret['FLAGS']) for uid, ret in data.items()}


class GmailCrispinClient(CrispinClient):
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
            Mapping of `uid` : GmailFlags.

        """
        data = self.conn.fetch(uids, ['FLAGS', 'X-GM-LABELS'])
        uid_set = set(uids)
        return {uid: GmailFlags(ret['FLAGS'],
                                self._decode_labels(ret['X-GM-LABELS']))
                for uid, ret in data.items() if uid in uid_set}

    def condstore_changed_flags(self, modseq):
        data = self.conn.fetch('1:*', ['FLAGS', 'X-GM-LABELS'],
                               modifiers=['CHANGEDSINCE {}'.format(modseq)])
        results = {}
        for uid, ret in data.items():
            if 'FLAGS' not in ret or 'X-GM-LABELS' not in ret:
                # We might have gotten an unsolicited fetch response that
                # doesn't have all the data we asked for -- if so, explicitly
                # fetch flags and labels for that UID.
                log.info('Got incomplete response in flags fetch', uid=uid,
                         ret=str(ret))
                data_for_uid = self.conn.fetch(uid, ['FLAGS', 'X-GM-LABELS'])
                if not data_for_uid:
                    continue
                ret = data_for_uid[uid]
            results[uid] = GmailFlags(ret['FLAGS'],
                                      self._decode_labels(ret['X-GM-LABELS']))
        return results

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
        raw_messages = self.conn.fetch(uids, ['BODY.PEEK[]', 'INTERNALDATE',
                                              'FLAGS', 'X-GM-THRID',
                                              'X-GM-MSGID', 'X-GM-LABELS'])

        messages = []
        uid_set = set(uids)
        for uid in sorted(raw_messages.iterkeys(), key=long):
            # Skip handling unsolicited FETCH responses
            if uid not in uid_set:
                continue
            msg = raw_messages[uid]
            messages.append(
                RawMessage(uid=long(uid),
                           internaldate=msg['INTERNALDATE'],
                           flags=msg['FLAGS'],
                           body=msg['BODY[]'],
                           g_thrid=long(msg['X-GM-THRID']),
                           g_msgid=long(msg['X-GM-MSGID']),
                           g_labels=self._decode_labels(msg['X-GM-LABELS'])))
        return messages

    def g_metadata(self, uids):
        """
        Download Gmail MSGIDs, THRIDs, and message sizes for the given uids.

        Parameters
        ----------
        uids : list
            UIDs to fetch data for. Must be from the selected folder.

        Returns
        -------
        dict
            uid: GMetadata(msgid, thrid, size)
        """
        # Super long sets of uids may fail with BAD ['Could not parse command']
        # In that case, just fetch metadata for /all/ uids.
        seqset = uids if len(uids) < 1e6 else '1:*'
        data = self.conn.fetch(seqset, ['X-GM-MSGID', 'X-GM-THRID',
                                        'RFC822.SIZE'])
        uid_set = set(uids)
        return {uid: GMetadata(ret['X-GM-MSGID'], ret['X-GM-THRID'],
                               ret['RFC822.SIZE'])
                for uid, ret in data.items() if uid in uid_set}

    def expand_thread(self, g_thrid):
        """
        Find all message UIDs in the selected folder with X-GM-THRID equal to
        g_thrid.

        Returns
        -------
        list
        """
        uids = [long(uid) for uid in
                self.conn.search(['X-GM-THRID', g_thrid])]
        # UIDs ascend over time; return in order most-recent first
        return sorted(uids, reverse=True)

    def find_by_header(self, header_name, header_value):
        return self.conn.search(['HEADER', header_name, header_value])

    def _decode_labels(self, labels):
        return map(imapclient.imap_utf7.decode, labels)
