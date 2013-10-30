from imapclient import IMAPClient

import datetime
import os

import time
import sessionmanager

from .log import get_logger
log = get_logger()

from ..util.misc import or_none
from ..util.cache import get_cache, set_cache

IMAP_HOST = 'imap.gmail.com'
SMTP_HOST = 'smtp.gmail.com'

class AuthFailure(Exception): pass
class TooManyConnectionsFailure(Exception): pass

### decorators

def timed(fn):
    """ A decorator for timing methods. """
    def timed_fn(self, *args, **kwargs):
        start_time = time.time()
        ret = fn(self, *args, **kwargs)
        self.log.info("\t\tTook %s seconds" %  str(time.time() - start_time))
        return ret
    return timed_fn

def connected(fn):
    """ A decorator for methods that can only be run on a logged-in client.
    """
    def connected_fn(self, *args, **kwargs):
        if self.server_needs_refresh():
            self._connect()
        ret = fn(self, *args, **kwargs)
        # a connected function did *something* with our connection, so
        # update the keepalive
        self.keepalive = datetime.datetime.utcnow()
        return ret
    return connected_fn

### main stuff

class NotImplementedError(Exception): pass

class CrispinError(Exception): pass

class CrispinClientBase(object):
    def __init__(self, account, cache=True):
        self.account = account
        self.log = get_logger(account)
        self.email_address = account.email_address
        self.oauth_token = account.o_access_token
        self.imap_server = None
        # last time the server checked in, in UTC
        self.keepalive = None
        # IMAP isn't stateless :(
        self.selected_folder = None
        self._all_mail_folder_name = None
        self.cache = cache

        self._connect()

    def set_cache(self, data, *keys):
        key = os.path.join('account.{0}'.format(self.account.id), *keys)
        return set_cache(key, data)

    def get_cache(self, *keys):
        return get_cache(
                os.path.join('account.{0}'.format(self.account.id), *keys))

    # XXX At some point we may want to query for a user's labels and sync
    # _all_ of them here. You can query gmail labels with
    # self.imap_server.list_folders() and filter out the [Gmail] folders
    @property
    def sync_folders(self):
        return ['Inbox', self.all_mail_folder_name()]

    @property
    def selected_folder_name(self):
        return or_none(self.selected_folder, lambda f: f[0])

    @property
    def selected_folder_info(self):
        return or_none(self.selected_folder, lambda f: f[1])

    @property
    def selected_highestmodseq(self):
        return or_none(self.selected_folder_info,
                lambda i: i['HIGHESTMODSEQ'])

    @property
    def selected_uidvalidity(self):
        return or_none(self.selected_folder_info,
                lambda i: long(i['UIDVALIDITY']))

    def _connect(self):
        raise NotImplementedError()

    def server_needs_refresh(self):
        raise NotImplementedError()

    def stop(self):
        raise NotImplementedError()

    def select_folder(self, folder):
        """ Selects a given folder and makes sure to set the 'folder_info'
            attribute to a (folder_name, select_info) pair.

            NOTE: The caller must ALWAYS validate UIDVALIDITY after calling
            this function. We don't do this here because this module
            deliberately doesn't deal with the database layer.
        """
        select_info = self.do_select_folder(folder)
        self.selected_folder = (folder, select_info)
        self.log.info('Selected folder {0} with {1} messages.'.format(
            folder, select_info['EXISTS']))
        return select_info

    def do_select_folder(self, folder):
        raise NotImplementedError()

    def all_uids(self):
        """ Get all UIDs associated with the currently selected folder as
            a list of integers sorted in ascending order.
        """
        data = self.fetch_all_uids()
        return sorted([int(s) for s in data])

    def fetch_all_uids(self):
        raise NotImplementedError()

    def g_msgids(self, uids=None):
        """ Download Gmail MSGIDs for the given messages, or all messages in
            the currently selected folder if no UIDs specified.

            The mapping must be uid->g_msgid and not vice-versa because a
            UID is unique (to a folder), but a g_msgid is not necessarily
            (it can legitimately appear twice in the folder).
        """
        self.log.info("Fetching X-GM-MSGID mapping from server.")
        if uids is None:
            uids = self.all_uids()
        return dict([(int(uid), unicode(ret['X-GM-MSGID'])) for uid, ret in \
                self.fetch_g_msgids(uids).iteritems()])

    def fetch_g_msgids(self, uids):
        raise NotImplementedError()

    def new_and_updated_uids(self, modseq):
        return self.fetch_new_and_updated_uids(modseq)

    def fetch_new_and_updated_uids(self, modseq):
        raise NotImplementedError()

    def flags(self, uids):
        return dict([(uid, msg['FLAGS']) for uid, msg in \
                self.fetch_flags(uids).iteritems()])

    def uids(self, uids):
        """ NOTE: This is a generator. """
        raw_messages = self.fetch_uids(uids)
        for uid in sorted(raw_messages.iterkeys(), key=int):
            msg = raw_messages[uid]
            # NOTE: python's email package (which lamson uses directly) needs
            # encoded bytestrings as its input, since to deal properly with
            # MIME-encoded email you need to do part decoding based on message
            # / MIME part headers anyway. imapclient tries to abstract away
            # bytes and decodes all bytes received from the wire as _latin-1_,
            # which is wrong in any case where 8bit MIME is used. so we have to
            # reverse the damage before we proceed.
            yield (int(uid), msg['INTERNALDATE'], msg['FLAGS'], msg['ENVELOPE'],
                    msg['BODY[]'].encode('latin-1'),
                    msg['X-GM-THRID'], msg['X-GM-MSGID'],
                    msg['X-GM-LABELS'])

    def all_mail_folder_name(self):
        """ This finds the Gmail "All Mail" folder name by using a flag.
            If the user's inbox is localized to a different language, it will
            return the proper localized string.

            An example response with some other flags:

            # * LIST (\HasNoChildren) "/" "INBOX"
            # * LIST (\Noselect \HasChildren) "/" "[Gmail]"
            # * LIST (\HasNoChildren \All) "/" "[Gmail]/All Mail"
            # * LIST (\HasNoChildren \Drafts) "/" "[Gmail]/Drafts"
            # * LIST (\HasNoChildren \Important) "/" "[Gmail]/Important"
            # * LIST (\HasNoChildren \Sent) "/" "[Gmail]/Sent Mail"
            # * LIST (\HasNoChildren \Junk) "/" "[Gmail]/Spam"
            # * LIST (\HasNoChildren \Flagged) "/" "[Gmail]/Starred"
            # * LIST (\HasNoChildren \Trash) "/" "[Gmail]/Trash"

            Caches the call since we use it all over the place and the
            folder is never going to change names on an open session.
        """
        if self._all_mail_folder_name is not None:
            return self._all_mail_folder_name
        folders = self.fetch_folder_list()
        for flags, delimiter, name in folders:
            if u'\\All' in flags:
                self._all_mail_folder_name = name
                return name
        raise CrispinError("Couldn't find All Mail folder")

class DummyCrispinClient(CrispinClientBase):
    """ A crispin client that doesn't actually use IMAP at all. Instead, it
        retrieves cached data from disk and allows one to "replay" previously
        cached actions.

        This allows us to rapidly iterate and debug the message ingester
        while offline, without hitting any IMAP API.
    """
    def _connect(self):
        pass

    def server_needs_refresh(self):
        return False

    def stop(self):
        pass

    def do_select_folder(self, folder):
        cached_data = self.get_cache(folder, 'select_info')

        assert cached_data is not None, \
                'no select_info cached for account {0} {1}'.format(
                        self.account.id, folder)
        return cached_data

    def fetch_all_uids(self):
        cached_data = self.get_cache(self.selected_folder_name, 'all_uids')

        assert cached_data is not None, \
                'no all_uids cached for account {0} {1}'.format(
                        self.account.id, self.selected_folder_name)
        return cached_data

    def fetch_g_msgids(self, uids):
        cached_data = self.get_cache(self.selected_folder_name, 'g_msgids')

        assert cached_data is not None, \
                'no g_msgids cached for account {0} {1}'.format(
                        self.account.id, self.selected_folder_name)
        return cached_data

    def fetch_new_and_updated_uids(self, modseq):
        cached_data = self.get_cache(self.selected_folder_name, 'updated', modseq)

        assert cached_data is not None, \
                'no modseq uids cached for account {0} {1} modseq {2}'.format(
                        self.account.id, self.selected_folder_name, modseq)
        return cached_data

    def fetch_flags(self, uids):
        # return { uid: data, uid: data }
        cached_data = dict()
        for uid in uids:
            cached_data[uid] = self.get_cache(
                    self.selected_folder_name,
                    self.selected_uidvalidity,
                    self.selected_highestmodseq,
                    uid, 'flags')

        assert cached_data, \
                'no flags cached for account {0} {1} uids {2}'.format(
                        self.account.id, self.selected_folder_name, uids)

        return cached_data

    def fetch_uids(self, uids):
        # return { uid: data, uid: data }
        cached_data = dict()
        for uid in uids:
            cached_data[uid] = self.get_cache(
                    self.selected_folder_name,
                    self.selected_uidvalidity,
                    self.selected_highestmodseq,
                    uid, 'body')

        assert cached_data, \
                'no body cached for account {0} {1} uids {2}'.format(
                        self.account.id, self.selected_folder_name, uids)

        return cached_data

    def fetch_folder_list(self):
        cached_data = self.get_cache('folders')

        assert cached_data is not None, \
                'no folder list cached for account {0}'.format(self.account.id)

        return cached_data

class CrispinClient(CrispinClientBase):
    """
    One thing to note about crispin clients is that *all* calls operate on
    the currently selected folder.

    Crispin will NEVER implicitly select a folder for you.

    This is very important! IMAP only guarantees that folder message UIDs
    are valid for a "session", which is defined as from the time you
    SELECT a folder until the connection is closed or another folder is
    selected.

    XXX: can we make it even harder to fuck this up?
    """
    # 20 minutes
    SERVER_TIMEOUT = datetime.timedelta(seconds=1200)
    # how many messages to download at a time
    CHUNK_SIZE = 20

    def _connect(self):
        self.log.info('Connecting to %s ...' % IMAP_HOST,)

        try:
            self.imap_server.noop()
            if self.imap_server.state == 'NONAUTH' or self.imap_server.state == 'LOGOUT':
                raise Exception
            self.log.info('Already connected to host.')
            return True
        # XXX eventually we want to do stricter exception-checking here
        except Exception, e:
            self.log.info('No active connection. Opening connection...')

        try:
            self.imap_server = IMAPClient(IMAP_HOST, use_uid=True,
                    ssl=True)
            # self.imap_server.debug = 4  # todo
            self.log.info("Logging in: %s" % self.email_address)
            self.imap_server.oauth2_login(self.email_address, self.oauth_token)

        except Exception as e:
            if str(e) == '[ALERT] Too many simultaneous connections. (Failure)':
                raise TooManyConnectionsFailure("Too many simultaneous connections.")
            elif str(e) == '[ALERT] Invalid credentials (Failure)':
                sessionmanager.verify_imap_account(self.account)
                raise AuthFailure("Invalid credentials")
            else:
                self.log.error(e)
                raise e

            self.imap_server = None
            return False

        self.keepalive = datetime.datetime.utcnow()
        self.log.info('Connection successful.')
        return True

    def server_needs_refresh(self):
        """ Many IMAP servers have a default minimum "no activity" timeout
            of 30 minutes. Sending NOPs ALL the time is hells slow, but we
            need to do it at least every 30 minutes.
        """
        now = datetime.datetime.utcnow()
        return self.keepalive is None or \
                (now - self.keepalive) > self.SERVER_TIMEOUT

    def stop(self):
        self.log.info("Closing connection.")
        if (self.imap_server):
            self.imap_server.logout()

    @connected
    @timed
    def do_select_folder(self, folder):
        try:
            select_info = self.imap_server.select_folder(folder, readonly=True)

            if self.cache:
                self.set_cache(select_info, folder, 'select_info')

            return select_info
        except Exception, e:
            self.log.error(e)
            raise e

    @connected
    def fetch_all_uids(self):
        data = self.imap_server.search(['NOT DELETED'])

        if self.cache:
            self.set_cache(data, self.selected_folder_name, 'all_uids')

        return data

    @connected
    def fetch_g_msgids(self, uids):
        data = self.imap_server.fetch(uids, ['X-GM-MSGID'])

        if self.cache:
            self.set_cache(data, self.selected_folder_name, 'g_msgids')

        return data

    @connected
    @timed
    def fetch_new_and_updated_uids(self, modseq):
        data = self.imap_server.search(['NOT DELETED', "MODSEQ {0}".format(modseq)])

        if self.cache:
            self.set_cache(data, self.selected_folder_name, 'updated', modseq)

        return data

    @connected
    def fetch_flags(self, uids):
        data = self.imap_server.fetch(uids, ['FLAGS'])

        if self.cache:
            # account.{{account_id}}/{{folder}}/{{uidvalidity}}/{{highestmodseq}}/{{uid}}/flags
            for uid in uids:
                self.set_cache(data[uid],
                        self.selected_folder_name,
                        self.selected_uidvalidity,
                        self.selected_highestmodseq,
                        uid, 'flags')

        return data

    @connected
    def fetch_uids(self, uids):
        data = self.imap_server.fetch(uids,
                ['BODY.PEEK[] ENVELOPE INTERNALDATE FLAGS', 'X-GM-THRID',
                 'X-GM-MSGID', 'X-GM-LABELS'])

        if self.cache:
            # account.{{account_id}}/{{folder}}/{{uidvalidity}}/{{highestmodseq}}/{{uid}}/flags
            for uid in uids:
                self.set_cache(data[uid],
                        self.selected_folder_name,
                        self.selected_uidvalidity,
                        self.selected_highestmodseq,
                        uid, 'body')

        return data

    @connected
    def fetch_folder_list(self):
        """ NOTE: XLIST is deprecated, so we just use LIST. """
        folders = self.imap_server.list_folders()

        if self.cache:
            self.set_cache(folders, 'folders')

        return folders
