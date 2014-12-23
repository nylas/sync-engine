""" IMAPClient wrapper for Inbox.

Unfortunately, due to IMAP's statefulness, to implement connection pooling we
have to shunt off dealing with the connection pool to the caller or we'll end
up trying to execute calls with the wrong folder selected some amount of the
time. That's why functions take a connection argument.
"""
import imaplib
import functools
import threading
from email.parser import HeaderParser

from collections import namedtuple, defaultdict

import gevent
from gevent import socket, GreenletExit
from gevent.coros import BoundedSemaphore

import geventconnpool

from inbox.util.concurrency import retry
from inbox.util.itert import chunk
from inbox.util.misc import or_none, timed
from inbox.basicauth import (ConnectionError, ValidationError,
                             TransientConnectionError, AuthError)
from inbox.models.session import session_scope
from inbox.models.account import Account
from inbox.models.backends.imap import ImapAccount

from inbox.log import get_logger
logger = get_logger()

__all__ = ['CrispinClient', 'GmailCrispinClient', 'CondStoreCrispinClient']

# Unify flags API across IMAP and Gmail
Flags = namedtuple('Flags', 'flags')
# Flags includes labels on Gmail because Gmail doesn't use \Draft.
GmailFlags = namedtuple('GmailFlags', 'flags labels')

GMetadata = namedtuple('GMetadata', 'msgid thrid')
RawMessage = namedtuple(
    'RawImapMessage',
    'uid internaldate flags body g_thrid g_msgid g_labels')

# We will retry a couple of times for transient errors, such as an invalid
# access token or the server being temporariliy unavailable.
MAX_TRANSIENT_ERRORS = 2

# Lazily-initialized map of account ids to lock objects.
# This prevents multiple greenlets from concurrently creating duplicate
# connection pools for a given account.
_lock_map = defaultdict(threading.Lock)


class GmailSettingError(Exception):
    """ Thrown on misconfigured Gmail accounts. """
    pass


def _get_connection_pool(account_id, pool_size, pool_map, readonly):
    with _lock_map[account_id]:
        try:
            pool = pool_map.get(account_id)
            return pool if pool else \
                pool_map.setdefault(
                    account_id,
                    CrispinConnectionPool(account_id,
                                          num_connections=pool_size,
                                          readonly=readonly))
        except AuthError:
            logger.error('Auth error for account {}'.format(account_id))
            raise GreenletExit()


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

CONN_DISCARD_EXC_CLASSES = (socket.error, imaplib.IMAP4.error)


class CrispinConnectionPool(geventconnpool.ConnectionPool):
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
        logger.info('Creating Crispin connection pool for account {} with {} '
                    'connections'.format(account_id, num_connections))
        self.account_id = account_id
        self.readonly = readonly
        self._new_conn_lock = BoundedSemaphore(1)
        self._set_account_info()

        # 1200s == 20min
        geventconnpool.ConnectionPool.__init__(
            self, num_connections, keepalive=1200,
            exc_classes=CONN_DISCARD_EXC_CLASSES)

    def _set_account_info(self):
        with session_scope() as db_session:
            account = db_session.query(Account).get(self.account_id)
            self.provider_name = account.provider
            self.email_address = account.email_address
            self.provider_info = account.provider_info
            self.imap_endpoint = account.imap_endpoint
            self.sync_state = account.sync_state

            if self.provider_name == 'gmail':
                self.client_cls = GmailCrispinClient
            elif getattr(account, 'supports_condstore', False):
                self.client_cls = CondStoreCrispinClient
            elif self.provider_info.get('condstore'):
                self.client_cls = CondStoreCrispinClient
            else:
                self.client_cls = CrispinClient

            # Refresh token if need be, for OAuthed accounts
            if self.provider_info['auth'] == 'oauth2':
                try:
                    self.credential = account.access_token
                except ValidationError:
                    logger.error("Error obtaining access token",
                                 account_id=self.account_id)
                    account.sync_state = 'invalid'
                    db_session.commit()
                    raise
                except ConnectionError:
                    logger.error("Error connecting",
                                 account_id=self.account_id)
                    account.sync_state = 'connerror'
                    db_session.commit()
                    raise
            else:
                self.credential = account.password

    def _new_connection(self):
        from inbox.auth import handler_from_provider

        # Ensure that connections are initialized serially, so as not to use
        # many db sessions on startup.
        with self._new_conn_lock as _:
            auth_handler = handler_from_provider(self.provider_name)

            for retry_count in range(MAX_TRANSIENT_ERRORS):
                try:
                    conn = auth_handler.connect_account(self.email_address,
                                                        self.credential,
                                                        self.imap_endpoint)

                    # If we can connect the account, then we can set the sate
                    # to 'running' if it wasn't already
                    if self.sync_state != 'running':
                        with session_scope() as db_session:
                            query = db_session.query(ImapAccount)
                            account = query.get(self.account_id)
                            self.sync_state = account.sync_state = 'running'
                    return self.client_cls(self.account_id, self.provider_info,
                                           self.email_address, conn,
                                           readonly=self.readonly)

                except ConnectionError, e:
                    if isinstance(e, TransientConnectionError):
                        return None
                    else:
                        logger.error('Error connecting',
                                     account_id=self.account_id)
                        with session_scope() as db_session:
                            query = db_session.query(ImapAccount)
                            account = query.get(self.account_id)
                            account.sync_state = 'connerror'
                        return None
                except ValidationError, e:
                    # If we failed to validate, but the account is oauth2, we
                    # may just need to refresh the access token. Try this one
                    # time.
                    if (self.provider_info['auth'] == 'oauth2' and
                            retry_count == 0):
                        with session_scope() as db_session:
                            query = db_session.query(ImapAccount)
                            account = query.get(self.account_id)
                            self.credential = account.renew_access_token()
                    else:
                        logger.error('Error validating',
                                     account_id=self.account_id)
                        with session_scope() as db_session:
                            query = db_session.query(ImapAccount)
                            account = query.get(self.account_id)
                            account.sync_state = 'invalid'
                        raise
            return None

    def _keepalive(self, c):
        c.conn.noop()


def _exc_callback():
    gevent.sleep(5)
    logger.info('Connection broken with error; retrying with new connection',
                exc_info=True)


def _fail_callback():
    logger.error('Max retries reached. Aborting', exc_info=True)


retry_crispin = functools.partial(
    retry, retry_classes=CONN_DISCARD_EXC_CLASSES, exc_callback=_exc_callback,
    fail_callback=_fail_callback, max_count=5, reset_interval=150)


class CrispinClient(object):
    """ Generic IMAP client wrapper.

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
        self.log = logger.new(account_id=account_id, module='crispin')
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
        folders = self.conn.list_folders()

        return folders

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
        select_info = self.conn.select_folder(
            folder, readonly=self.readonly)
        select_info['UIDVALIDITY'] = long(select_info['UIDVALIDITY'])
        self.selected_folder = (folder, select_info)
        # don't propagate cached information from previous session
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
        to_sync = []
        folders = self.folder_names()
        for tag in ('inbox', 'drafts', 'sent', 'starred', 'important',
                    'archive', 'extra', 'spam', 'trash'):
            if tag == 'extra' and tag in folders:
                to_sync.extend(folders['extra'])
            elif tag in folders:
                to_sync.append(folders[tag])
        return to_sync

    def folder_names(self):
        # Different providers have different names for folders, here
        # we have a default map for common name mapping, additional
        # mappings can be provided via the provider configuration file
        default_folder_map = {'INBOX': 'inbox', 'DRAFTS': 'drafts',
                              'DRAFT': 'drafts', 'JUNK': 'spam',
                              'ARCHIVE': 'archive', 'SENT': 'sent',
                              'TRASH': 'trash', 'SPAM': 'spam'}

        # Some providers also provide flags to determine common folders
        # Here we read these flags and apply the mapping
        flag_to_folder_map = {'\\Trash': 'trash', '\\Sent': 'sent',
                              '\\Drafts': 'drafts', '\\Junk': 'spam',
                              '\\Inbox': 'inbox', '\\Spam': 'spam'}

        # Additionally we provide a custom mapping for providers that
        # don't fit into the defaults.
        folder_map = self.provider_info.get('folder_map', {})

        if self._folder_names is None:
            folders = self._fetch_folder_list()
            self._folder_names = dict()
            for flags, delimiter, name in folders:
                if u'\\Noselect' in flags:
                    # special folders that can't contain messages
                    pass
                # TODO: internationalization support
                elif name in folder_map:
                    self._folder_names[folder_map[name]] = name
                elif name.upper() in default_folder_map:
                    self._folder_names[default_folder_map[name.upper()]] = name
                else:
                    matched = False
                    for flag in flags:
                        if flag in flag_to_folder_map:
                            self._folder_names[flag_to_folder_map[flag]] = name
                            matched = True
                    if not matched:
                        self._folder_names.setdefault(
                            'extra', list()).append(name)

        # TODO: support subfolders
        return self._folder_names

    def folder_status(self, folder):
        status = [long(val) for val in self.conn.folder_status(
            folder, ('UIDVALIDITY'))]

        return status

    def create_folder(self, name):
        self.conn.create_folder(name)

    def search_uids(self, criteria):
        """ Find not-deleted UIDs in this folder matching the criteria.

        See http://tools.ietf.org/html/rfc3501.html#section-6.4.4 for valid
        criteria.
        """
        full_criteria = ['NOT DELETED']
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
        data = self.conn.search(['NOT DELETED'])
        return sorted([long(s) for s in data])

    def uids(self, uids):
        uids = [str(u) for u in uids]
        raw_messages = self.conn.fetch(uids,
                                       ['BODY.PEEK[] INTERNALDATE FLAGS'])
        for uid, msg in raw_messages.iteritems():
            if 'BODY[]' not in msg:
                raise Exception(
                    'No BODY[] element in IMAP response. Tags given: {}'
                    .format(msg.keys()))
            # NOTE: flanker needs encoded bytestrings as its input, since to
            # deal properly with MIME-encoded email you need to do part
            # decoding based on message / MIME part headers anyway. imapclient
            # tries to abstract away bytes and decodes all bytes received from
            # the wire as _latin-1_, which is wrong in any case where 8bit MIME
            # is used. so we have to reverse the damage before we proceed.
            #
            # We should REMOVE this XXX HACK XXX when we finish working with
            # Menno to fix this problem upstream.
            msg['BODY[]'] = msg['BODY[]'].encode('latin-1')

        messages = []
        for uid in sorted(raw_messages.iterkeys(), key=long):
            msg = raw_messages[uid]
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
        uids = [str(u) for u in uids]
        data = self.conn.fetch(uids, ['FLAGS'])
        return dict([(long(uid), Flags(msg['FLAGS']))
                     for uid, msg in data.iteritems()])

    def copy_uids(self, uids, to_folder):
        if not uids:
            return
        uids = [str(u) for u in uids]
        self.conn.copy(uids, to_folder)

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
        assert self.selected_folder_name == self.folder_names()['drafts'], \
            'Must select drafts folder first ({0})'.format(
                self.selected_folder_name)

        self.conn.append(self.selected_folder_name, message, ['\\Draft'], date)

    def create_message(self, message, date=None):
        """Create a message on the server. Only used to fix server-side bugs,
        like iCloud not saving Sent messages"""
        assert self.selected_folder_name == self.folder_names()['sent'], \
            'Must select sent folder first ({0})'.format(
                self.selected_folder_name)

        self.conn.append(self.selected_folder_name, message, [], date)

    def fetch_headers(self, uids):
        """Fetch headers for the given uids. Chunked because certain providers
        fail with 'Command line too large' if you feed them too many uids at
        once."""
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
        """Delete a draft, as identified either by its X-Inbox-Id or by its
        Message-Id header. We first delete the message from the Drafts folder,
        and then also delete it from the Trash folder if necessary."""
        drafts_folder_name = self.folder_names()['drafts']
        trash_folder_name = self.folder_names()['trash']
        self.conn.select_folder(drafts_folder_name)
        self._delete_message(inbox_uid, message_id_header)
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
            self.log.error('No remote messages found to delete',
                           inbox_uid=inbox_uid,
                           message_id_header=message_id_header)
            return
        if len(matching_uids) > 1:
            self.log.error('Multiple remote messages found to delete',
                           inbox_uid=inbox_uid,
                           message_id_header=message_id_header,
                           uids=matching_uids)
            return
        self.conn.delete_messages(matching_uids)
        self.conn.expunge()


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
        """ Gmail-specific list of folders to sync.

        In Gmail, every message is a subset of All Mail, with the exception of
        the Trash and Spam folders. So we only sync All Mail, Trash, Spam,
        and Inbox (for quickly downloading initial inbox messages and
        continuing to receive new Inbox messages while a large mail archive is
        downloading).

        Returns
        -------
        list
            Folders to sync (as strings).
        """
        if 'all' not in self.folder_names():
            raise GmailSettingError(
                "Account {} ({}) has no detected 'All Mail' folder. This is "
                "probably because it is disabled from appearing in IMAP. "
                "Please enable at "
                "https://mail.google.com/mail/#settings/labels"
                .format(self.account_id, self.email_address))
        folders = [self.folder_names()['all']]
        # Non-essential folders, so don't error out if they're not present.
        for tag in ('trash', 'spam'):
            if tag in self.folder_names():
                folders.append(self.folder_names()[tag])
        return folders

    def flags(self, uids):
        """ Gmail-specific flags.

        Returns
        -------
        dict
            Mapping of `uid` (str) : GmailFlags.
        """
        uids = [str(u) for u in uids]
        data = self.conn.fetch(uids, ['FLAGS X-GM-LABELS'])
        return dict([(long(uid), GmailFlags(msg['FLAGS'], msg['X-GM-LABELS']))
                     for uid, msg in data.iteritems()])

    def g_msgids(self, uids):
        """ X-GM-MSGIDs for the given UIDs.

        Returns
        -------
        dict
            Mapping of `uid` (long) : `g_msgid` (long)
        """
        uids = [str(u) for u in uids]
        data = self.conn.fetch(uids, ['X-GM-MSGID'])
        return dict([(long(uid), long(d['X-GM-MSGID']))
                     for uid, d in data.iteritems()])

    def folder_names(self):
        """ Parses out Gmail-specific folder names based on Gmail IMAP flags.

        If the user's account is localized to a different language, it will
        return the proper localized string.

        Caches the call since we use it all over the place and folders never
        change names during a session.
        """
        if self._folder_names is None:
            folders = self._fetch_folder_list()
            self._folder_names = dict()
            for flags, delimiter, name in folders:
                if u'\\Noselect' in flags:
                    # special folders that can't contain messages, usually
                    # just '[Gmail]'
                    pass
                elif '\\All' in flags:
                    self._folder_names['all'] = name
                elif name.lower() == 'inbox':
                    self._folder_names[name.lower()] = name.capitalize()
                    continue
                else:
                    for flag in ['\\Drafts', '\\Important', '\\Sent', '\\Junk',
                                 '\\Flagged', '\\Trash']:
                        # find localized names for Gmail's special folders
                        if flag in flags:
                            k = flag.replace('\\', '').lower()
                            if k == 'flagged':
                                self._folder_names['starred'] = name
                            elif k == 'junk':
                                self._folder_names['spam'] = name
                            else:
                                self._folder_names[k] = name
                            break
                    else:
                        # everything else is a label
                        self._folder_names.setdefault('labels', list())\
                            .append(name)
            if 'labels' in self._folder_names:
                self._folder_names['labels'].sort()
                # synonyms on Gmail
                self._folder_names['extra'] = self._folder_names['labels']
        return self._folder_names

    def uids(self, uids):
        uids = [str(u) for u in uids]
        raw_messages = self.conn.fetch(uids, ['BODY.PEEK[] INTERNALDATE FLAGS',
                                              'X-GM-THRID', 'X-GM-MSGID',
                                              'X-GM-LABELS'])
        for uid, msg in raw_messages.iteritems():
            # NOTE: flanker needs encoded bytestrings as its input, since to
            # deal properly with MIME-encoded email you need to do part
            # decoding based on message / MIME part headers anyway. imapclient
            # tries to abstract away bytes and decodes all bytes received from
            # the wire as _latin-1_, which is wrong in any case where 8bit MIME
            # is used. so we have to reverse the damage before we proceed.
            #
            # We should REMOVE this XXX HACK XXX when we finish working with
            # Menno to fix this problem upstream.
            msg['BODY[]'] = msg['BODY[]'].encode('latin-1')

        messages = []
        for uid in sorted(raw_messages.iterkeys(), key=long):
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
        uids = [str(u) for u in uids]
        self.log.debug('fetching X-GM-MSGID and X-GM-THRID',
                       uid_count=len(uids))
        return dict([(long(uid), GMetadata(long(ret['X-GM-MSGID']),
                                           long(ret['X-GM-THRID']))) for uid,
                     ret in self.conn.fetch(uids, ['X-GM-MSGID',
                                                   'X-GM-THRID']).iteritems()])

    def expand_thread(self, g_thrid):
        """ Find all message UIDs in this account with X-GM-THRID equal to
        g_thrid.

        Requires the "All Mail" folder to be selected.

        Returns
        -------
        list
            All Mail UIDs (as integers), sorted most-recent first.
        """
        assert self.selected_folder_name == self.folder_names()['all'], \
            "must select All Mail first ({})".format(
                self.selected_folder_name)
        criterion = 'X-GM-THRID {}'.format(g_thrid)
        uids = [long(uid) for uid in self.conn.search(['NOT DELETED',
                                                       criterion])]
        # UIDs ascend over time; return in order most-recent first
        return sorted(uids, reverse=True)

    def find_messages(self, g_thrid):
        """ Get UIDs for the [sub]set of messages belonging to the given thread
            that are in the current folder.
        """
        criteria = 'X-GM-THRID {}'.format(g_thrid)
        return sorted([long(uid) for uid in
                       self.conn.search(['NOT DELETED', criteria])])

    # -----------------------------------------
    # following methods WRITE to IMAP account!
    # -----------------------------------------

    def archive_thread(self, g_thrid):
        assert self.selected_folder_name == self.folder_names()['inbox'], \
            "must select INBOX first ({0})".format(self.selected_folder_name)
        uids = self.find_messages(g_thrid)
        # delete from inbox == archive for Gmail
        if uids:
            self.conn.delete_messages(uids)

    def copy_thread(self, g_thrid, to_folder):
        """ NOTE: Does nothing if the thread isn't in the currently selected
            folder.
        """
        uids = self.find_messages(g_thrid)
        if uids:
            self.conn.copy(uids, to_folder)

    def add_label(self, g_thrid, label_name):
        """
        NOTE: Does nothing if the thread isn't in the currently selected
        folder.

        """
        uids = self.find_messages(g_thrid)
        self.conn.add_gmail_labels(uids, [label_name])

    def remove_label(self, g_thrid, label_name):
        """
        NOTE: Does nothing if the thread isn't in the currently selected
        folder.

        """
        # Gmail won't even include the label of the selected folder (when the
        # selected folder is a label) in the list of labels for a UID, FYI.
        assert self.selected_folder_name != label_name, \
            "Gmail doesn't support removing a selected label"
        uids = self.find_messages(g_thrid)
        self.conn.remove_gmail_labels(uids, [label_name])

    def get_labels(self, g_thrid):
        uids = self.find_messages(g_thrid)
        labels = self.conn.get_gmail_labels(uids)

        # the complicated list comprehension below simply flattens the list
        unique_labels = set([item for sublist in labels.values()
                             for item in sublist])
        return list(unique_labels)

    def set_unread(self, g_thrid, unread):
        uids = self.find_messages(g_thrid)
        if unread:
            self.conn.remove_flags(uids, ['\\Seen'])
        else:
            self.conn.add_flags(uids, ['\\Seen'])

    def set_starred(self, g_thrid, starred):
        uids = self.find_messages(g_thrid)
        if starred:
            self.conn.add_flags(uids, ['\\Flagged'])
        else:
            self.conn.remove_flags(uids, ['\\Flagged'])

    def delete(self, g_thrid, folder_name):
        """
        Permanent delete i.e. remove the corresponding label and add the
        `Trash` flag. We currently only allow this for Drafts, all other
        non-All Mail deletes are archives.

        """
        uids = self.find_messages(g_thrid)

        if folder_name == self.folder_names()['drafts']:
            # Remove Gmail's `Draft` label
            self.conn.remove_gmail_labels(uids, ['\Draft'])

            # Move to Gmail's `Trash` folder
            self.conn.delete_messages(uids)
            self.conn.expunge()

            # Delete from `Trash`
            self.conn.select_folder(self.folder_names()['trash'])

            trash_uids = self.find_messages(g_thrid)
            self.conn.delete_messages(trash_uids)
            self.conn.expunge()

    def find_by_header(self, header_name, header_value):
        criteria = ['NOT DELETED',
                    'HEADER {} {}'.format(header_name, header_value)]
        return self.conn.search(criteria)
