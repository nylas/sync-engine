# allow imports from the top-level dir (we will want to make the package
# system better later)

from imapclient import IMAPClient

import datetime
import logging as log

import encoding
from models import MessageMeta, BlockMeta, FolderMeta
import time
import json
import sessionmanager

from itertools import chain

from quopri import decodestring as quopri_decodestring
from base64 import b64decode
from chardet import detect as detect_charset

from .util.misc import or_none
from hashlib import sha256

IMAP_HOST = 'imap.gmail.com'
SMTP_HOST = 'smtp.gmail.com'

class AuthFailure(Exception): pass
class TooManyConnectionsFailure(Exception): pass

### generators

def messages_from_raw(raw_messages):
    for uid in sorted(raw_messages.iterkeys(), key=int):
        msg = raw_messages[uid]
        # NOTE: python's email package (which lamson uses directly) needs
        # encoded bytestrings as its input, since to deal properly with
        # MIME-encoded email you need to do part decoding based on message /
        # MIME part headers anyway. imapclient tries to abstract away bytes and
        # decodes all bytes received from the wire as _latin-1_, which is wrong
        # in any case where 8bit MIME is used. so we have to reverse the damage
        # before we proceed.
        yield (int(uid), msg['INTERNALDATE'], msg['FLAGS'], msg['ENVELOPE'],
                msg['BODY[]'].encode('latin-1'),
                msg['X-GM-THRID'], msg['X-GM-MSGID'],
                msg['X-GM-LABELS'])

### decorators

def print_duration(fn):
    """ A decorator for timing methods. """
    def connected_fn(self, *args, **kwargs):
        start_time = time.time()
        ret = fn(self, *args, **kwargs)
        log.info("\t\tTook %s seconds" %  str(time.time() - start_time))
        return ret
    return connected_fn

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

class CrispinClientBase(object):
    def __init__(self, user):
        self.user = user
        self.email_address = user.g_email
        self.oauth_token = user.g_access_token
        self.imap_server = None
        # last time the server checked in, in UTC
        self.keepalive = None
        # IMAP isn't stateless :(
        self.selected_folder = None
        self._all_mail_folder_name = None

        self._connect()

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

    def fetch_g_msgids(self, uids=None):
        raise Exception("Subclass must implement")

    def all_uids(self):
        raise Exception("Subclass must implement")

    def server_needs_refresh(self):
        raise Exception("Subclass must implement")

    def _connect(self):
        raise Exception("Subclass must implement")

    def stop(self):
        raise Exception("Subclass must implement")

    def select_folder(self):
        """ Selects a given folder and makes sure to set the 'folder_info'
            attribute to a (folder_name, select_info) pair.
        """
        raise Exception("Subclass must implement")

    def select_all_mail(self):
        return self.select_folder(self.all_mail_folder_name())

    def fetch_metadata(self, uids):
        raise Exception("Subclass must implement")

    def fetch_uids(self, uids):
        raise Exception("Subclass must implement")

    def all_mail_folder_name(self):
        raise Exception("Subclass must implement")

class DummyCrispinClient(CrispinClientBase):
    """ A crispin client that doesn't actually use IMAP at all. Instead, it
        retrieves RawMessage objects from either local disk or a remote block
        store (S3).

        This allows us to rapidly iterate and debug the message ingester
        without hosing the IMAP API for test accounts.
    """
    def server_needs_refresh(self):
        return False

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

    def fetch_g_msgids(self, uids=None):
        """ Download Gmail MSGIDs for the given messages, or all messages in
            the currently selected folder if no UIDs specified.

            The mapping must be uid->g_msgid and not vice-versa because a
            UID is unique (to a folder), but a g_msgid is not necessarily
            (it can legitimately appear twice in the folder).
        """
        log.info("Fetching X-GM-MSGID mapping from server.")
        if uids is None:
            uids = self.all_uids()
        return dict([(int(uid), unicode(ret['X-GM-MSGID'])) for uid, ret in \
                self.imap_server.fetch(uids, ['X-GM-MSGID']).iteritems()])

    def all_uids(self):
        """ Get all UIDs associated with the currently selected folder as
            a list of integers sorted in ascending order.
        """
        return sorted([int(s) for s in self.imap_server.search(['NOT DELETED'])])

    def server_needs_refresh(self):
        """ Many IMAP servers have a default minimum "no activity" timeout
            of 30 minutes. Sending NOPs ALL the time is hells slow, but we
            need to do it at least every 30 minutes.
        """
        now = datetime.datetime.utcnow()
        return self.keepalive is None or \
                (now - self.keepalive) > self.SERVER_TIMEOUT

    def _connect(self):
        log.info('Connecting to %s ...' % IMAP_HOST,)

        try:
            self.imap_server.noop()
            if self.imap_server.state == 'NONAUTH' or self.imap_server.state == 'LOGOUT':
                raise Exception
            log.info('Already connected to host.')
            return True
        # XXX eventually we want to do stricter exception-checking here
        except Exception, e:
            log.info('No active connection. Opening connection...')

        try:
            self.imap_server = IMAPClient(IMAP_HOST, use_uid=True,
                    ssl=True)
            # self.imap_server.debug = 4  # todo
            log.info("Logging in: %s" % self.email_address)
            self.imap_server.oauth2_login(self.email_address, self.oauth_token)

        except Exception as e:
            if str(e) == '[ALERT] Too many simultaneous connections. (Failure)':
                raise TooManyConnectionsFailure("Too many simultaneous connections.")
            elif str(e) == '[ALERT] Invalid credentials (Failure)':
                sessionmanager.verify_user(self.user)
                raise AuthFailure("Invalid credentials")
            else:
                raise e
                log.error(e)

            self.imap_server = None
            return False

        self.keepalive = datetime.datetime.utcnow()
        log.info('Connection successful.')
        return True

    def stop(self):
        log.info("Closing connection.")
        if (self.imap_server):
            self.imap_server.logout()


    @connected
    @print_duration
    def get_changed_uids(self, modseq):
        return self.imap_server.search(['NOT DELETED', "MODSEQ {0}".format(modseq)])

    @connected
    @print_duration
    def select_folder(self, folder):
        """ NOTE: The caller must ALWAYS validate UIDVALIDITY after calling
            this function. We don't do this here because this module
            deliberately doesn't deal with the database layer.
        """
        try:
            select_info = self.imap_server.select_folder(folder, readonly=True)
            self.selected_folder = (folder, select_info)
        except Exception, e:
            log.error(e)
            raise e
        log.info('Selected folder %s with %d messages.' % (folder, select_info['EXISTS']) )
        return select_info

    @connected
    def fetch_metadata(self, uids):
        raw_messages = self.imap_server.fetch(uids, ['FLAGS'])
        return dict([(uid, msg['FLAGS']) for uid, msg in raw_messages.iteritems()])

    @connected
    def fetch_uids(self, UIDs):
        """ Downloads entire messages for the given UIDs, parses them,
            and creates metadata database entries and writes mail parts
            to disk.
        """
        UIDs = [u for u in UIDs if int(u) != 6372]
        # log.info("{0} downloading {1}".format(self.user.g_email, UIDs))
        query = 'BODY.PEEK[] ENVELOPE INTERNALDATE FLAGS'
        raw_messages = self.imap_server.fetch(UIDs,
                [query, 'X-GM-THRID', 'X-GM-MSGID', 'X-GM-LABELS'])

        # { 'msgid': { 'meta': MessageMeta, 'parts': [BlockMeta, ...] } }
        messages = dict()
        new_foldermeta = []
        for uid, internaldate, flags, envelope, body, x_gm_thrid, x_gm_msgid, \
                x_gm_labels in messages_from_raw(raw_messages):
            mailbase = encoding.from_string(body)
            new_msg = MessageMeta()
            new_msg.data_sha256 = sha256(body).hexdigest()
            new_msg.g_user_id = self.user.g_user_id
            new_msg.namespace_id = self.user.root_namespace_id
            new_msg.g_email = self.user.g_email
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
            new_msg.from_addr = envelope[2]
            new_msg.sender_addr = envelope[3]
            new_msg.reply_to = envelope[4]
            new_msg.to_addr = envelope[5]
            new_msg.cc_addr = envelope[6]
            new_msg.bcc_addr = envelope[7]
            new_msg.in_reply_to = envelope[8]
            new_msg.message_id = envelope[9]

            new_msg.internaldate = internaldate
            new_msg.g_thrid = unicode(x_gm_thrid)
            new_msg.g_msgid = unicode(x_gm_msgid)

            fm = FolderMeta(namespace_id=self.user.root_namespace_id,
                    folder_name=self.selected_folder_name,
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


            messages.setdefault(new_msg.g_msgid, dict())['meta'] = new_msg

            i = 0  # for walk_index

            # Store all message headers as object with index 0
            headers_part = BlockMeta()
            headers_part.messagemeta = new_msg
            headers_part.walk_index = i
            headers_part._data = json.dumps(mailbase.headers)
            headers_part.data_sha256 = sha256(headers_part._data).hexdigest()
            messages[new_msg.g_msgid].setdefault('parts', []).append(headers_part)

            extra_parts = []

            if mailbase.body:
                # single-part message?
                extra_parts.append(mailbase)

            for part in chain(extra_parts, mailbase.walk()):
                i += 1
                mimepart = encoding.to_message(part)
                if mimepart.is_multipart(): continue  # TODO should we store relations?

                new_part = BlockMeta()
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
Parsed Content-Disposition was: '{3}'""".format(uid, self.selected_folder_name,
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
                messages[new_msg.g_msgid]['parts'].append(new_part)

        return messages, new_foldermeta

    @connected
    def all_mail_folder_name(self):
        """ Note: XLIST is deprecated, so we just use LIST

            This finds the Gmail "All Mail" folder name by using a flag.
            If the user's inbox is localized to a different language, it will return
            the proper localized string.

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
            folder is never going to change names on an open session
        """
        if self._all_mail_folder_name is not None:
            return self._all_mail_folder_name
        else:
            resp = self.imap_server.list_folders()
            folders =  [dict(flags = f[0], delimiter = f[1],
                name = f[2]) for f in resp]
            for f in folders:
                if u'\\All' in f['flags']:
                    return f['name']
            raise Exception("Couldn't find All Mail folder")
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
