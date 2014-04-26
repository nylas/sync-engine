""" IMAPClient wrapper for Inbox.

Unfortunately, due to IMAP's statefulness, to implement connection pooling we
have to shunt off dealing with the connection pool to the caller or we'll end
up trying to execute calls with the wrong folder selected some amount of the
time. That's why functions take a connection argument.
"""

from collections import namedtuple

from inbox.server.log import get_logger
from inbox.server.pool import get_connection_pool

from inbox.util.misc import or_none, timed

__all__ = ['CrispinClient', 'GmailCrispinClient', 'YahooCrispinClient']

# Unify flags API across IMAP and Gmail
Flags = namedtuple("Flags", "flags")
# Flags includes labels on Gmail because Gmail doesn't use \Draft.
GmailFlags = namedtuple("GmailFlags", "flags labels")

GMetadata = namedtuple('GMetadata', 'msgid thrid')
RawMessage = namedtuple(
    'RawImapMessage',
    'uid internaldate flags body g_thrid g_msgid g_labels created')


def new_crispin(account_id, provider, conn_pool_size=None, readonly=True):
    crispin_module_for = dict(Gmail=GmailCrispinClient, IMAP=CrispinClient,
                              Yahoo=YahooCrispinClient)

    cls = crispin_module_for[provider]
    return cls(account_id, conn_pool_size=conn_pool_size, readonly=readonly)


class CrispinClient(object):
    """ Generic IMAP client wrapper.

    One thing to note about crispin clients is that *all* calls operate on
    the currently selected folder.

    Crispin will NEVER implicitly select a folder for you.

    This is very important! IMAP only guarantees that folder message UIDs
    are valid for a "session", which is defined as from the time you
    SELECT a folder until the connection is closed or another folder is
    selected.

    Methods must be called using a connection from the pool, e.g.

        @retry_crispin
        def poll():
            with instance.pool.get() as c:
                instance.all_uids(c)

    We don't save c on instances to save messiness with garbage
    collection of connections.

    Pool connections have to be managed by the crispin caller because
    of IMAP's stateful sessions.

    Parameters
    ----------
    account_id : int
        Database id of the associated IMAPAccount.
    conn_pool_size : int
        Number of IMAPClient connections to pool.
    readonly : bool
        Whether or not to open IMAP connections as readonly.
    """
    PROVIDER = 'IMAP'

    def __init__(self, account_id, conn_pool_size=None, readonly=True):
        self.log = get_logger(account_id)
        self.account_id = account_id
        # IMAP isn't stateless :(
        self.selected_folder = None
        self._folder_names = None
        self.conn_pool_size = conn_pool_size
        self.pool = get_connection_pool(account_id, conn_pool_size)
        self.readonly = readonly

    def select_folder(self, folder, uidvalidity_cb, c):
        """ Selects a given folder.

        Makes sure to set the 'selected_folder' attribute to a
        (folder_name, select_info) pair.

        Selecting a folder indicates the start of an IMAP session.  IMAP UIDs
        are only guaranteed valid for sessions, so the caller must provide a
        callback that checks UID validity.

        Is a NOOP if `folder` is already selected.
        """
        if self.selected_folder_name != folder:
            select_info = c.select_folder(folder, readonly=self.readonly)
            self.selected_folder = (folder, select_info)
            # don't propagate cached information from previous session
            self._folder_names = None
            self.log.info('Selected folder {0} with {1} messages.'.format(
                folder, select_info['EXISTS']))
            return uidvalidity_cb(folder, select_info)
        else:
            return self.selected_folder_info

    @property
    def selected_folder_name(self):
        return or_none(self.selected_folder, lambda f: f[0])

    @property
    def selected_folder_info(self):
        return or_none(self.selected_folder, lambda f: f[1])

    @property
    def selected_highestmodseq(self):
        return or_none(self.selected_folder_info, lambda i: i['HIGHESTMODSEQ'])

    @property
    def selected_uidvalidity(self):
        return or_none(self.selected_folder_info, lambda i:
                       long(i['UIDVALIDITY']))

    def sync_folders(self, c):
        # TODO: probabaly all of the folders
        raise NotImplementedError

    def folder_names(self, c):
        # TODO: parse out contents of non-Gmail-specific LIST
        raise NotImplementedError

    def _fetch_folder_list(self, c):
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
        folders = c.list_folders()

        return folders

    def folder_status(self, folder, c):
        status = c.folder_status(folder,
                                 ('UIDVALIDITY', 'HIGHESTMODSEQ', 'UIDNEXT'))

        return status

    def next_uid(self, folder, c):
        status = self.folder_status(folder, c)
        return status['UIDNEXT']

    def search_uids(self, criteria, c):
        """ Find not-deleted UIDs in this folder matching the criteria.

        See http://tools.ietf.org/html/rfc3501.html#section-6.4.4 for valid
        criteria.
        """
        full_criteria = ['NOT DELETED']
        if isinstance(criteria, list):
            full_criteria.extend(criteria)
        else:
            full_criteria.append(criteria)
        return c.search(full_criteria)

    def all_uids(self, c):
        """ Fetch all UIDs associated with the currently selected folder.

        Returns
        -------
        list
            UIDs as integers sorted in ascending order.
        """
        data = c.search(['NOT DELETED'])
        return sorted([long(s) for s in data])

    @timed
    def new_and_updated_uids(self, modseq, c):
        return c.search(['NOT DELETED', "MODSEQ {0}".format(modseq)])


class YahooCrispinClient(CrispinClient):
    """ NOTE: This implementation is NOT FINISHED. """
    def __init__(self, account_id, conn_pool_size=None, readonly=True):
        # CrispinClient.__init__(self, account_id, conn_pool_size=conn_pool_size,
        #                        readonly=readonly)
        # TODO: Remove this once this client is usable.
        raise NotImplementedError

    def sync_folders(self, c):
        return self.folder_names(c)

    def flags(self, uids, c):
        data = c.fetch(uids, ['FLAGS'])
        return dict([(uid, Flags(msg['FLAGS']))
                     for uid, msg in data.iteritems()])

    def folder_names(self, c):
        if self._folder_names is None:
            folders = self._fetch_folder_list(c)
            self._folder_names = [name for flags, delimiter, name in folders]
        return self._folder_names

    def uids(self, uids, c):
        raw_messages = c.fetch(uids,
                               ['BODY.PEEK[] INTERNALDATE FLAGS'])
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
        for uid in sorted(raw_messages.iterkeys(), key=int):
            msg = raw_messages[uid]
            messages.append(RawMessage(uid=int(uid),
                                       internaldate=msg['INTERNALDATE'],
                                       flags=msg['FLAGS'],
                                       body=msg['BODY[]']))
        return messages

    def expand_threads(self, thread_ids, c):
        NotImplementedError


class GmailCrispinClient(CrispinClient):
    PROVIDER = 'Gmail'

    def __init__(self, account_id, conn_pool_size=None, readonly=True):
        CrispinClient.__init__(self, account_id, conn_pool_size=conn_pool_size,
                               readonly=readonly)

    def sync_folders(self, c):
        """ Gmail-specific list of folders to sync.

        In Gmail, every message is a subset of All Mail, so we only sync that
        folder + Inbox (for quickly downloading initial inbox messages and
        continuing to receive new Inbox messages while a large mail archive is
        downloading).

        Returns
        -------
        list
            Folders to sync (as strings).
        """
        return [self.folder_names(c)['inbox'], self.folder_names(c)['all']]

    def flags(self, uids, c):
        """ Gmail-specific flags.

        Returns
        -------
        dict
            Mapping of `uid` (str) : GmailFlags.
        """
        data = c.fetch(uids, ['FLAGS X-GM-LABELS'])
        return dict([(uid, GmailFlags(msg['FLAGS'], msg['X-GM-LABELS']))
                     for uid, msg in data.iteritems()])

    def folder_names(self, c):
        """ Parses out Gmail-specific folder names based on Gmail IMAP flags.

        If the user's account is localized to a different language, it will
        return the proper localized string.

        Caches the call since we use it all over the place and folders never
        change names during a session.
        """
        if self._folder_names is None:
            folders = self._fetch_folder_list(c)
            self._folder_names = dict()
            for flags, delimiter, name in folders:
                if u'\\Noselect' in flags:
                    # special folders that can't contain messages, usually
                    # just '[Gmail]'
                    pass
                elif '\\All' in flags:
                    self._folder_names['archive'] = name
                    self._folder_names['all'] = name
                elif name.lower() == 'inbox':
                    self._folder_names[name.lower()] = name
                    continue
                else:
                    for flag in ['\\Drafts', '\\Important', '\\Sent', '\\Junk',
                                 '\\Flagged', '\\Trash']:
                        # find localized names for Gmail's special folders
                        if flag in flags:
                            k = flag.replace('\\', '').lower()
                            self._folder_names[k] = name
                            break
                    else:
                        # everything else is a label
                        self._folder_names.setdefault('labels', list())\
                            .append(name)
            if 'labels' in self._folder_names:
                self._folder_names['labels'].sort()
        return self._folder_names

    def uids(self, uids, c):
        raw_messages = c.fetch(uids,
                               ['BODY.PEEK[] INTERNALDATE FLAGS', 'X-GM-THRID',
                                'X-GM-MSGID', 'X-GM-LABELS'])
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
        for uid in sorted(raw_messages.iterkeys(), key=int):
            msg = raw_messages[uid]
            messages.append(RawMessage(uid=int(uid),
                                       internaldate=msg['INTERNALDATE'],
                                       flags=msg['FLAGS'],
                                       body=msg['BODY[]'],
                                       g_thrid=msg['X-GM-THRID'],
                                       g_msgid=msg['X-GM-MSGID'],
                                       g_labels=msg['X-GM-LABELS'],
                                       created=False))
        return messages

    def g_metadata(self, uids, c):
        """ Download Gmail MSGIDs and THRIDs for the given messages.

        NOTE: only UIDs are guaranteed to be unique to a folder, X-GM-MSGID
        and X-GM-THRID may not be.

        Parameters
        ----------
        uids : list
            UIDs to fetch data for. Must be from the selected folder.
        c : IMAPClient
            IMAP connection to use.

        Returns
        -------
        dict
            uid: GMetadata(msgid, thrid)
        """
        self.log.info("Fetching X-GM-MSGID and X-GM-THRID mapping from server.")
        return dict([(long(uid), GMetadata(str(ret['X-GM-MSGID']),
                                           str(ret['X-GM-THRID']))) for uid,
                     ret in c.fetch(uids,
                                    ['X-GM-MSGID', 'X-GM-THRID']).iteritems()])

    def expand_threads(self, g_thrids, c):
        """ Find all message UIDs in this account with X-GM-THRID in g_thrids.

        Requires the "All Mail" folder to be selected.

        Returns
        -------
        list
            All Mail UIDs (as integers), sorted most-recent first.
        """
        assert self.selected_folder_name == self.folder_names(c)['all'], \
            "must select All Mail first ({0})".format(
                self.selected_folder_name)
        criteria = ('OR ' * (len(g_thrids)-1)) + ' '.join(
            ['X-GM-THRID {0}'.format(thrid) for thrid in g_thrids])
        uids = [int(uid) for uid in c.search(['NOT DELETED', criteria])]
        # UIDs ascend over time; return in order most-recent first
        return sorted(uids, reverse=True)

    def find_messages(self, g_thrid, c):
        """ Get UIDs for the [sub]set of messages belonging to the given thread
            that are in the current folder.
        """
        criteria = 'X-GM-THRID {0}'.format(g_thrid)
        return c.search(['NOT DELETED', criteria])

    ### the following methods WRITE to the IMAP account!

    def archive_thread(self, g_thrid, c):
        assert self.selected_folder_name == self.folder_names(c)['inbox'], \
            "must select INBOX first ({0})".format(self.selected_folder_name)
        uids = self.find_messages(g_thrid, c)
        # delete from inbox == archive for Gmail
        if uids:
            c.delete_messages(uids)

    def copy_thread(self, g_thrid, to_folder, c):
        """ NOTE: Does nothing if the thread isn't in the currently selected
            folder.
        """
        uids = self.find_messages(g_thrid, c)
        if uids:
            c.copy(uids, to_folder)

    def add_label(self, g_thrid, label_name, c):
        """ NOTE: Does nothing if the thread isn't in the currently selected
            folder.
        """
        uids = self.find_messages(g_thrid, c)
        c.add_gmail_labels(uids, [label_name])

    def remove_label(self, g_thrid, label_name, c):
        """ NOTE: Does nothing if the thread isn't in the currently selected
            folder.
        """
        # Gmail won't even include the label of the selected folder (when the
        # selected folder is a laebl) in the list of labels for a UID, FYI.
        assert self.selected_folder_name != label_name, \
            "Gmail doesn't support removing a selected label"
        uids = self.find_messages(g_thrid, c)
        c.remove_gmail_labels(uids, [label_name])
