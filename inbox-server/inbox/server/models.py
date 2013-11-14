import os
import re
import json

from email.utils import parseaddr, getaddresses

from sqlalchemy.interfaces import PoolListener

from sqlalchemy import Column, Integer, String, DateTime, Date, Boolean, Enum
from sqlalchemy import create_engine, ForeignKey, Text, Index, func, event
from sqlalchemy import distinct
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import reconstructor, relationship, backref, sessionmaker
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
Base = declarative_base()

from hashlib import sha256

from boto.s3.connection import S3Connection
from boto.s3.key import Key

from ..util.file import mkdirp, remove_file, Lock
from ..util.html import strip_tags, plaintext2html
from ..util.misc import or_none
from .config import config, is_prod
from .log import get_logger
log = get_logger()

import encoding

from urllib import quote_plus as urlquote

from itertools import chain
from quopri import decodestring as quopri_decodestring
from base64 import b64decode
from chardet import detect as detect_charset

### Roles

class JSONSerializable(object):
    def cereal(self):
        """ Override this and return a string of the object serialized for
            the web client.
        """
        raise NotImplementedError("cereal not implemented")

STORE_MSG_ON_S3 = True

class Blob(object):
    """ A blob of data that can be saved to local or remote (S3) disk. """
    size = Column(Integer, default=0)
    data_sha256 = Column(String(64))
    def save(self, data):
        assert data is not None, \
                "Blob can't have NoneType data (can be zero-length, though!)"
        assert type(data) is not unicode, "Blob bytes must be encoded"
        self.size = len(data)
        self.data_sha256 = sha256(data).hexdigest()
        if self.size > 0:
            if STORE_MSG_ON_S3:
                self._save_to_s3(data)
            else:
                self._save_to_disk(data)
        else:
            log.warning("Not saving 0-length {1} {0}".format(
                self.id, self.__class__.__name__))

    def get_data(self):
        if self.size == 0:
            log.warning("block size is 0")
            # NOTE: This is a placeholder for "empty bytes". If this doesn't
            # work as intended, it will trigger the hash assertion later.
            data = ""
        elif hasattr(self, '_data'):
            # on initial download we temporarily store data in memory
            data = self._data
        elif STORE_MSG_ON_S3:
            data = self._get_from_s3()
        else:
            data = self._get_from_disk()
        assert self.data_sha256 == sha256(data).hexdigest(), \
                "Returned data doesn't match stored hash!"
        return data

    def delete_data(self):
        if self.size == 0:
            # nothing to do here
            return
        if STORE_MSG_ON_S3:
            self._delete_from_s3()
        else:
            self._delete_from_disk()
        # TODO should we clear these fields?
        # self.size = None
        # self.data_sha256 = None

    def _save_to_s3(self, data):
        assert len(data) > 0, "Need data to save!"
        # TODO: store AWS credentials in a better way.
        assert 'AWS_ACCESS_KEY_ID' in config, "Need AWS key!"
        assert 'AWS_SECRET_ACCESS_KEY' in config, "Need AWS secret!"
        assert 'MESSAGE_STORE_BUCKET_NAME' in config, "Need bucket name to store message data!"
        # Boto pools connections at the class level
        conn = S3Connection(config.get('AWS_ACCESS_KEY_ID'),
                            config.get('AWS_SECRET_ACCESS_KEY'))
        bucket = conn.get_bucket(config.get('MESSAGE_STORE_BUCKET_NAME'))

        # See if it alreays exists and has the same hash
        data_obj = bucket.get_key(self.data_sha256)
        if data_obj:
            assert data_obj.get_metadata('data_sha256') == self.data_sha256, \
                "Block hash doesn't match what we previously stored on s3!"
            # log.info("Block already exists on S3.")
            return

        data_obj = Key(bucket)
        # if metadata:
        #     assert type(metadata) is dict
        #     for k, v in metadata.iteritems():
        #         data_obj.set_metadata(k, v)
        data_obj.set_metadata('data_sha256', self.data_sha256)
        # data_obj.content_type = self.content_type  # Experimental
        data_obj.key = self.data_sha256
        # log.info("Writing data to S3 with hash {0}".format(self.data_sha256))
        # def progress(done, total):
        #     log.info("%.2f%% done" % (done/total * 100) )
        # data_obj.set_contents_from_string(data, cb=progress)
        data_obj.set_contents_from_string(data)

    def _get_from_s3(self):
        assert self.data_sha256, "Can't get data with no hash!"
        # Boto pools connections at the class level
        conn = S3Connection(config.get('AWS_ACCESS_KEY_ID'),
                            config.get('AWS_SECRET_ACCESS_KEY'))
        bucket = conn.get_bucket(config.get('MESSAGE_STORE_BUCKET_NAME'))
        data_obj = bucket.get_key(self.data_sha256)
        assert data_obj, "No data returned!"
        return data_obj.get_contents_as_string()

    def _delete_from_s3(self):
        # TODO
        pass

    # Helpers
    @property
    def _data_file_directory(self):
        assert self.data_sha256
        # Nest it 6 items deep so we don't have folders with too many files.
        h = self.data_sha256
        return os.path.join('/mnt', 'parts', h[0], h[1], h[2], h[3], h[4], h[5])

    @property
    def _data_file_path(self):
        return os.path.join(self._data_file_directory, self.data_sha256)

    def _save_to_disk(self, data):
        mkdirp(self._data_file_directory)
        with open(self._data_file_path, 'wb') as f:
            f.write(data)

    def _get_from_disk(self):
        try:
            with open(self._data_file_path, 'rb') as f:
                return f.read()
        except Exception:
            log.error("No data for hash {0}".format(self.data_sha256))
            # XXX should this instead be empty bytes?
            return None

    def _delete_from_disk(self):
        remove_file(self._data_file_path)

### Column Types

# http://docs.sqlalchemy.org/en/rel_0_9/core/types.html#marshal-json-strings
class JSON(TypeDecorator):
    impl = Text

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if not value:
            return None
        return json.loads(value)

### Tables

# global

class IMAPAccount(Base):
    __tablename__ = 'imapaccount'
    id = Column(Integer, primary_key=True, autoincrement=True)
    # user_id refers to Inbox's user id
    user_id = Column(Integer, ForeignKey('user.id', ondelete='CASCADE'),
            nullable=False)
    user = relationship("User", backref="imapaccounts")

    # http://stackoverflow.com/questions/386294/what-is-the-maximum-length-of-a-valid-email-address
    email_address = Column(String(254), nullable=True, index=True)
    provider = Column(Enum('Gmail', 'Outlook', 'Yahoo', 'Inbox'), nullable=False)

    # local flags & data
    save_raw_messages = Column(Boolean, default=True)

    sync_host = Column(String(255), nullable=True)
    last_synced_contacts = Column(DateTime, nullable=True)

    @property
    def sync_active(self):
        return self.sync_host is not None

    # oauth stuff (most providers support oauth at this point, shockingly)
    # TODO figure out the actual lengths of these
    # XXX we probably don't actually need to save all of this crap
    # XXX encrypt some of this crap?
    o_token_issued_to = Column(String(512))
    o_user_id = Column(String(512))
    o_access_token = Column(String(1024))
    o_id_token = Column(String(1024))
    o_expires_in = Column(Integer)
    o_access_type = Column(String(512))
    o_token_type = Column(String(512))
    o_audience = Column(String(512))
    o_scope = Column(String(512))
    o_refresh_token = Column(String(512))
    o_verified_email = Column(Boolean)

    # used to verify key lifespan
    date = Column(DateTime)

    @property
    def _sync_lockfile_name(self):
        return "/var/lock/inbox_sync/{0}.lock".format(self.id)

    @property
    def _sync_lock(self):
        return Lock(self._sync_lockfile_name, block=False)

    def sync_lock(self):
        self._sync_lock.acquire()

    def sync_unlock(self):
        self._sync_lock.release()

    def total_stored_data(self):
        """ Computes the total size of the block data of emails in your
            account's IMAP folders
        """
        subq = db_session.query(Block) \
                .join(Block.message, Message.folderitems) \
                .filter(FolderItem.imapaccount_id==self.id) \
                .group_by(Message.id, Block.id)
        return db_session.query(func.sum(subq.subquery().columns.size)).scalar()

    def total_stored_messages(self):
        """ Computes the number of emails in your account's IMAP folders """
        return db_session.query(Message) \
                .join(Message.folderitems) \
                .filter(FolderItem.imapaccount_id==self.id) \
                .group_by(Message.id).count()

    def all_uids(self, folder_name):
        return [uid for uid, in
                db_session.query(FolderItem.msg_uid).filter_by(
                    imapaccount_id=self.id, folder_name=folder_name)]

    def all_g_msgids(self):
        return set([g_msgid for g_msgid, in
            db_session.query(distinct(Message.g_msgid))\
                    .join(FolderItem).filter(
                FolderItem.imapaccount_id==self.id)])

    def update_metadata(self, folder_name, uids, new_flags):
        """ Update flags (the only metadata that can change). """
        for fm in db_session.query(FolderItem).filter(
                FolderItem.imapaccount_id==self.id,
                FolderItem.msg_uid.in_(uids),
                FolderItem.folder_name==folder_name):
            sorted_flags = sorted(new_flags[fm.msg_uid])
            if fm.flags != sorted_flags:
                fm.flags = sorted_flags
                db_session.add(fm)
        db_session.commit()

    def remove_messages(self, uids, folder):
        fm_query = db_session.query(FolderItem).filter(
                FolderItem.imapaccount_id==self.id,
                FolderItem.folder_name==folder,
                FolderItem.msg_uid.in_(uids))
        fm_query.delete(synchronize_session='fetch')

        # not sure if this one is actually needed - does delete() automatically
        # commit?
        db_session.commit()

        # XXX TODO: Have a recurring worker permanently remove dangling
        # messages from the database and block store. (Probably too
        # expensive to do here.)

    def get_uidvalidity(self, folder_name):
        try:
            # using .one() here may catch duplication bugs
            return db_session.query(UIDValidity).filter_by(
                    imapaccount=self, folder_name=folder_name).one()
        except NoResultFound:
            return None

    def uidvalidity_valid(self, selected_uidvalidity, \
            folder_name, cached_uidvalidity=None):
        """ Validate UIDVALIDITY on currently selected folder. """
        if cached_uidvalidity is None:
            cached_uidvalidity = self.get_uidvalidity(folder_name).uid_validity
            assert type(cached_uidvalidity) == type(selected_uidvalidity), \
                    "cached_validity: {0} / selected_uidvalidity: {1}".format(
                            type(cached_uidvalidity),
                            type(selected_uidvalidity))

        if cached_uidvalidity is None:
            # no row is basically equivalent to UIDVALIDITY == -inf
            return True
        else:
            return selected_uidvalidity >= cached_uidvalidity

    def messages_from_raw(self, folder_name, raw_messages):
        """ Parses message data for the given UIDs, creates metadata database
            entries, computes threads, and writes mail parts to disk.

            Returns two lists: one of new Message objects, and one of new
            FolderItem objects. Neither list of objects has been committed.
            Block objects are implicitly returned via Message associations.

            Threads are not computed here; you gotta do that separately.
        """
        new_messages = []
        new_folderitems = []
        for uid, internaldate, flags, body, x_gm_thrid, x_gm_msgid, \
                x_gm_labels in raw_messages:
            mailbase = encoding.from_string(body)
            new_msg = Message()
            new_msg.data_sha256 = sha256(body).hexdigest()
            new_msg.namespace_id = self.namespace.id
            new_msg.uid = uid

            subject = mailbase.headers.get('Subject')
            if subject is None:
                new_msg.subject = ''
            else:
                # Headers will wrap when longer than 78 chars per RFC822_2
                new_msg.subject = re.sub(r'\s?\n\t\s?|\s?\r\n\s?', '', subject)

            new_msg.from_addr = or_none(encoding.encode_contacts([
                parseaddr(mailbase.headers.get('From'))]), lambda a: a[0])
            new_msg.sender_addr = or_none(encoding.encode_contacts([
                parseaddr(mailbase.headers.get('Sender'))]), lambda a: a[0])
            new_msg.reply_to = or_none(encoding.encode_contacts([
                parseaddr(mailbase.headers.get('Reply-To'))]), lambda a: a[0])
            new_msg.to_addr = or_none(mailbase.headers.get('To'),
                    lambda h: encoding.encode_contacts(getaddresses([h])))
            new_msg.cc_addr = or_none(mailbase.headers.get('Cc'),
                    lambda h: encoding.encode_contacts(getaddresses([h])))
            new_msg.bcc_addr = or_none(mailbase.headers.get('Bcc'),
                    lambda h: encoding.encode_contacts(getaddresses([h])))
            new_msg.in_reply_to = mailbase.headers.get('In-Reply-To')
            new_msg.message_id = mailbase.headers.get('Message-Id')

            new_msg.internaldate = internaldate
            new_msg.g_msgid = x_gm_msgid
            # NOTE: this value is not saved to the database, but it is used
            # later for thread detection after message download
            new_msg._g_thrid = x_gm_thrid

            # TODO optimize storage of flags with a bit field or something,
            # if we actually care.
            # \Seen     Message has been read
            # \Answered Message has been answered
            # \Flagged  Message is "flagged" for urgent/special attention
            # \Deleted  Message is "deleted" for removal by later EXPUNGE
            # \Draft    Message has not completed composition (marked as a draft).
            # \Recent   session is the first session to have been notified
            #           about this message
            fm = FolderItem(imapaccount_id=self.id, folder_name=folder_name,
                    msg_uid=uid, message=new_msg, flags=sorted(flags))
            new_folderitems.append(fm)

            new_msg.size = len(body)  # includes headers text

            new_messages.append(new_msg)

            i = 0  # for walk_index

            # Store all message headers as object with index 0
            headers_part = Block()
            headers_part.message = new_msg
            headers_part.walk_index = i
            headers_part._data = json.dumps(mailbase.headers)
            headers_part.size = len(headers_part._data)
            headers_part.data_sha256 = sha256(headers_part._data).hexdigest()
            new_msg.parts.append(headers_part)

            extra_parts = []

            if mailbase.body:
                # single-part message
                extra_parts.append(mailbase)

            for part in chain(extra_parts, mailbase.walk()):
                i += 1
                mimepart = encoding.to_message(part)
                if mimepart.is_multipart():
                    continue  # TODO should we store relations?

                new_part = Block()
                new_part.message = new_msg
                new_part.walk_index = i
                new_part.misc_keyval = mimepart.items()  # everything

                content_type = mimepart.get_content_type()
                # Content-Type
                try:
                    assert content_type == mimepart.get_params()[0][0],\
                    "Content-Types not equal! {0} and {1}".format(
                            content_type, mimepart.get_params()[0][0])
                except Exception:
                    log.error("Content-Types not equal: {0}".format(
                        mimepart.get_params()))

                new_part.content_type = mimepart.get_content_type()

                # File attachments
                filename = mimepart.get_filename(failobj=None)
                new_part.filename = or_none(filename,
                        lambda fn: encoding.properly_decode_header(fn))

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
    Parsed Content-Disposition was: '{3}'""".format(uid, folder_name,
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
                data_encoding = mimepart.get('Content-Transfer-Encoding',
                        None).lower()

                if data_encoding == 'quoted-printable':
                    data_to_write = quopri_decodestring(payload_data)
                elif data_encoding == 'base64':
                    data_to_write = b64decode(payload_data)
                elif data_encoding == '7bit' or data_encoding == '8bit':
                    # Need to get charset and decode with that too.
                    charset = str(mimepart.get_charset())
                    if charset == 'None':
                        charset = None  # bug
                    try:
                        assert charset
                        payload_data = encoding.attempt_decoding(charset, payload_data)
                    except Exception, e:
                        detected_charset = detect_charset(payload_data)
                        detected_charset_encoding = detected_charset['encoding']
                        log.error("{0} Failed decoding with {1}. Now trying {2}"\
                                .format(e, charset, detected_charset_encoding))
                        try:
                            payload_data = encoding.attempt_decoding(
                                    detected_charset_encoding, payload_data)
                        except Exception, e:
                            log.error("That failed too. Hmph. Not sure how to recover here")
                            raise e
                        log.info("Success!")
                    data_to_write = payload_data.encode('utf-8', errors='strict')
                else:
                    raise Exception("Unknown encoding scheme:" + str(encoding))

                new_part._data = data_to_write
                new_part.size = len(data_to_write)
                new_part.data_sha256 = sha256(data_to_write).hexdigest()
                new_msg.parts.append(new_part)
            new_msg.calculate_sanitized_body()
            new_msg.calculate_snippet()

        return new_messages, new_folderitems

class UserSession(Base):
    """ Inbox-specific sessions. """
    __tablename__ = 'user_session'

    id = Column(Integer, primary_key=True, autoincrement=True)

    token = Column(String(40))

    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    user = relationship('User', backref='sessions')

class Namespace(Base):
    """ A way to do grouping / permissions, basically. """
    __tablename__ = 'namespace'
    id = Column(Integer, primary_key=True, autoincrement=True)
    # NOTE: only root namespaces have IMAP accounts
    imapaccount_id = Column(Integer, ForeignKey('imapaccount.id',
        ondelete='CASCADE'), nullable=True)
    imapaccount = relationship('IMAPAccount', backref=backref('namespace',
        uselist=False)) # really the root_namespace
    # TODO should have a name that defaults to gmail

    # invariant: imapaccount is non-null iff namespace_type is root
    namespace_type = Column(Enum('root', 'shared_folder', 'todo'),
            nullable=False, default='root')

    @property
    def email_address(self):
        if self.imapaccount is not None:
            return self.imapaccount.email_address

    def threads_for_folder(self, folder_name):
        return db_session.query(Thread).join(Thread.messages).join(FolderItem) \
              .filter(FolderItem.folder_name == folder_name,
                      Message.namespace_id == self.id,
                      FolderItem.message_id == Message.id).all()

    def cereal(self):
        return dict(id=self.id, name='Gmail')

class SharedFolder(Base):
    __tablename__ = 'sharedfolder'

    id = Column(Integer, primary_key=True, autoincrement=True)

    namespace = relationship('Namespace', backref='sharedfolders')
    namespace_id = Column(Integer, ForeignKey('namespace.id'), nullable=False)
    user = relationship('User', backref='sharedfolders')
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)

    display_name = Column(String(40))

    def cereal(self):
        return dict(id=self.id, name=self.display_name)

class User(Base):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True, autoincrement=True)

    name = Column(String(255))

class Contact(Base):
    """ Inbox-specific sessions. """
    __tablename__ = 'contact'

    id = Column(Integer, primary_key=True, autoincrement=True)

    imapaccount_id = Column(ForeignKey('imapaccount.id', ondelete='CASCADE'),
            nullable=False)
    imapaccount = relationship("IMAPAccount")

    g_id = Column(String(64))
    source = Column("source", Enum("local", "remote"))

    email_address = Column(String(254), nullable=True, index=True)
    name = Column(Text)
    # phone_number = Column(String(64))

    updated_at = Column(DateTime, default=func.now(),
                        onupdate=func.current_timestamp())
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (UniqueConstraint('g_id', 'source', 'imapaccount_id'),)

    def cereal(self):
        return dict(id=self.id,
                    email=self.email_address,
                    name=self.name)

    def __repr__(self):
        # XXX this won't work properly with unicode (e.g. in the name)
        return str(self.name) + ", " + str(self.email) + ", " + str(self.source)

# sharded (by namespace)

class Message(JSONSerializable, Base):
    __tablename__ = 'message'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # XXX clean this up a lot - make a better constructor, maybe taking
    # a mailbase as an argument to prefill a lot of attributes

    namespace_id = Column(ForeignKey('namespace.id'), nullable=False)
    namespace = relationship("Namespace", backref="messages",
            order_by="Message.internaldate")

    thread_id = Column(Integer, ForeignKey('thread.id'), nullable=False)
    thread = relationship('Thread', backref="messages",
            order_by="Message.internaldate")

    # TODO probably want to store some of these headers in a better
    # non-pickled way to provide indexing and human-readability
    from_addr = Column(JSON, nullable=True)
    sender_addr = Column(JSON, nullable=True)
    reply_to = Column(JSON, nullable=True)
    to_addr = Column(JSON, nullable=True)
    cc_addr = Column(JSON, nullable=True)
    bcc_addr = Column(JSON, nullable=True)
    in_reply_to = Column(JSON, nullable=True)
    message_id = Column(String(255), nullable=False)
    # XXX TODO this can actually be nullable (and fix messages_from_raw too)
    subject = Column(Text, nullable=False)
    internaldate = Column(DateTime, nullable=False)
    size = Column(Integer, default=0, nullable=False)
    data_sha256 = Column(String(255), nullable=True)

    # Most messages are short and include a lot of quoted text. Preprocessing
    # just the relevant part out makes a big difference in how much data we
    # need to send over the wire.
    # Maximum length is determined by typical email size limits (25 MB body +
    # attachments) on Gmail), assuming a maximum # of chars determined by
    # 1-byte (ASCII) chars.
    # NOTE: always HTML :)
    sanitized_body = Column(Text(length=26214400), nullable=False)
    snippet = Column(String(191), nullable=False)

    # we had to replace utf-8 errors before writing... this might be a
    # mail-parsing bug, or just a message from a bad client.
    decode_error = Column(Boolean, default=False, nullable=False)

    # only on messages from Gmail
    g_msgid = Column(String(40), nullable=True)

    def calculate_sanitized_body(self):
        plain_part, html_part = self.body()
        if html_part:
            # self.sanitized_body = html_part.split('<div class="gmail_quote">')[0]
            self.sanitized_body = html_part
        elif plain_part is None:
            self.sanitized_body = ''
        else:
            self.sanitized_body = plaintext2html(plain_part)

    def calculate_snippet(self):
        assert self.sanitized_body is not None, \
                "need sanitized_body to calculate snippet"
        # No need to strip newlines since HTML won't display them anyway.
        stripped = strip_tags(self.sanitized_body)
        # truncate based on decoded version so as not to accidentally truncate
        # mid-codepoint
        self.snippet = stripped.decode('utf-8')[:191].encode('utf-8')

    def body(self):
        """ Returns (plaintext, html) body for the message. """
        assert self.parts, \
                "Can't calculate body before parts have been parsed"

        plain_data = None
        html_data = None

        for part in self.parts:
            if part.content_type == 'text/html':
                html_data = part.get_data()
                break
        for part in self.parts:
            if part.content_type == 'text/plain':
                plain_data = part.get_data()
                break

        return plain_data, html_data

    def trimmed_subject(self):
        s = self.subject
        if s[:4] == u'RE: ' or s[:4] == u'Re: ' :
            s = s[4:]
        return s

    @property
    def prettified_body(self):
        html_data = self.sanitized_body

        prettified = None
        if 'font:' in html_data or 'font-face:' \
                in html_data or 'font-family:' in html_data:
            prettified = html_data
        else:
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "message_template.html")
            with open(path, 'r') as f:
                # template has %s in it. can't do format because python
                # misinterprets css
                prettified = f.read() % html_data

        return prettified

    def cereal(self):
        # TODO serialize more here for client API
        d = {}
        d['from'] = self.from_addr
        d['to'] = self.to_addr
        d['date'] = self.internaldate
        d['subject'] = self.subject
        d['id'] = self.id
        d['thread_id'] = self.thread_id
        d['namespace_id'] = self.namespace_id
        d['snippet'] = self.snippet
        d['body'] = self.prettified_body
        return d

# These are the top 15 most common Content-Type headers
# in my personal mail archive. --mg
common_content_types = ['text/plain',
                        'text/html',
                        'multipart/alternative',
                        'multipart/mixed',
                        'image/jpeg',
                        'multipart/related',
                        'application/pdf',
                        'image/png',
                        'image/gif',
                        'application/octet-stream',
                        'multipart/signed',
                        'application/msword',
                        'application/pkcs7-signature',
                        'message/rfc822',
                        'image/jpg']

class Block(JSONSerializable, Blob, Base):
    __tablename__ = 'block'
    """ Metadata for message parts stored in s3 """

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, ForeignKey('message.id'), nullable=False)
    message = relationship('Message', backref="parts")

    walk_index = Column(Integer)
    # Save some space with common content types
    _content_type_common = Column(Enum(*common_content_types))
    _content_type_other = Column(String(255))
    filename = Column(String(255))

    content_disposition = Column(Enum('inline', 'attachment'))
    content_id = Column(String(255))  # For attachments
    misc_keyval = Column(JSON)

    is_inboxapp_attachment = Column(Boolean, default=False)
    collection_id = Column(Integer, ForeignKey("collections.id"), nullable=True)
    collection = relationship('Collection', backref="blocks")

    # TODO: create a constructor that allows the 'content_type' keyword

    __table_args__ = (UniqueConstraint('message_id', 'walk_index', 'data_sha256'),)

    def __init__(self, *args, **kwargs):
        self.content_type = None
        self.size = 0
        Base.__init__(self, *args, **kwargs)

    def __repr__(self):
        return 'Block: %s' % self.__dict__

    def client_json(self):
        d = {}
        d['g_id'] = self.message.g_msgid
        d['g_index'] = self.walk_index
        d['content_type'] = self.content_type
        d['content_disposition'] = self.content_disposition
        d['size'] = self.size
        d['filename'] = self.filename
        return d

    @reconstructor
    def init_on_load(self):
        if self._content_type_common:
            self.content_type = self._content_type_common
        else:
            self.content_type = self._content_type_other

@event.listens_for(Block, 'before_insert', propagate = True)
def serialize_before_insert(mapper, connection, target):
    if target.content_type in common_content_types:
        target._content_type_common = target.content_type
        target._content_type_other = None
    else:
        target._content_type_common = None
        target._content_type_other = target.content_type

class FolderItem(JSONSerializable, Base):
    __tablename__ = 'folderitem'
    """ This maps folder names to UIDs in that folder. """

    id = Column(Integer, primary_key=True, autoincrement=True)

    imapaccount_id = Column(ForeignKey('imapaccount.id', ondelete='CASCADE'),
            nullable=False)
    imapaccount = relationship("IMAPAccount")
    message_id = Column(Integer, ForeignKey('message.id'), nullable=False)
    message = relationship('Message')
    msg_uid = Column(Integer, nullable=False)
    # maximum Gmail label length is 225 (tested empirically), but constraining
    # folder_name uniquely requires max length of 767 bytes under utf8mb4
    # http://mathiasbynens.be/notes/mysql-utf8mb4
    folder_name = Column(String(191), nullable=False)
    # NOTE: We could definitely make this field smaller than Text.
    flags = Column(JSON, nullable=False)

    __table_args__ = (UniqueConstraint('folder_name', 'msg_uid', 'imapaccount_id',),)

# make pulling up all messages in a given folder fast
Index('folderitem_imapaccount_id_folder_name', FolderItem.imapaccount_id,
        FolderItem.folder_name)

class UIDValidity(JSONSerializable, Base):
    __tablename__ = 'uidvalidity'
    """ UIDValidity has a per-folder value. If it changes, we need to
        re-map g_msgid to UID for that folder.
    """

    id = Column(Integer, primary_key=True, autoincrement=True)
    imapaccount_id = Column(ForeignKey('imapaccount.id', ondelete='CASCADE'),
            nullable=False)
    imapaccount = relationship("IMAPAccount")
    # maximum Gmail label length is 225 (tested empirically), but constraining
    # folder_name uniquely requires max length of 767 bytes under utf8mb4
    # http://mathiasbynens.be/notes/mysql-utf8mb4
    folder_name = Column(String(191), nullable=False)
    uid_validity = Column(Integer, nullable=False)
    highestmodseq = Column(Integer, nullable=False)

    __table_args__ = (UniqueConstraint('imapaccount_id', 'folder_name'),)

class Collection(Base):
    __tablename__ = 'collections'
    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String(32), nullable=True)

class TodoItem(JSONSerializable, Base):
    __tablename__ = 'todoitem'
    """ Each todo item has a row in TodoItem described the item's metadata.
        Additionally, for each thread that is a todo item, all messages within
        that thread should be in the user's todo namespace.
    """

    id = Column(Integer, primary_key=True, autoincrement=True)

    thread_id = Column(ForeignKey('thread.id', ondelete='CASCADE'),
            nullable=False)
    thread = relationship("Thread", backref="todo_item")

    # Gmail thread IDs are only unique per-account, so in order to de-dupe, we
    # need to store the account that this thread came from. When we get a
    # Thread database table, these two lines can go.
    imapaccount_id = Column(ForeignKey('imapaccount.id', ondelete='CASCADE'),
            nullable=False)
    imapaccount = relationship("IMAPAccount")

    # this must be a namespace of the todo type
    namespace_id = Column(ForeignKey('namespace.id'), nullable=False)
    namespace = relationship("Namespace", backref="todo_items")

    # the todo item description (defaults to the email's subject but can be changed)
    display_name = Column(String(255), nullable=False)

    # TODO possibly in the future we'll want to store richer metadata about
    # these due dates (eg, convert each into a # of days)
    due_date = Column(Enum('Today', 'Soon'), nullable=False)

    # if completed: the date on which the task was completed
    # a null value indicates an incomplete task
    date_completed = Column(Date, nullable=True)

    @property
    def completed(self):
        return self.date_completed is not None

    # within a due date, items will be sorted by increasing sort_index
    sort_index = Column(Integer, nullable=False)

    def cereal(self):
        return dict(
                id             = self.id,
                display_name   = self.display_name,
                due_date       = self.due_date,
                completed      = self.date_completed is not None,
                date_completed = self.date_completed,
                sort_index     = self.sort_index,
                # NOTE: eventually we may want to have some sort of thread
                # cache layer on the client and just serialize the id instead
                thread         = self.thread.cereal(),
            )

class TodoNamespace(JSONSerializable, Base):
    __tablename__ = 'todonamespace'
    """ A 1-1 mapping between users and their todo namespaces """

    id = Column(Integer, primary_key=True, autoincrement=True)

    namespace = relationship('Namespace',
            backref=backref('todo_namespace', uselist=False))
    namespace_id = Column(Integer, ForeignKey('namespace.id'), nullable=False,
            unique=True)

    user = relationship('User', backref=backref('todo_namespace', uselist=False))
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False, unique=True)

    def cereal(self):
        return dict(id=self.id)

class Thread(JSONSerializable, Base):
    """ Pre-computed thread metadata.

    (We have all this information elsewhere, but it's not as nice to use.)
    """
    __tablename__ = 'thread'

    id = Column(Integer, primary_key=True, autoincrement=True)

    subject = Column(Text, nullable=False)
    subjectdate = Column(DateTime, nullable=False)
    recentdate = Column(DateTime, nullable=False)

    # makes pulling up threads in a folder simple / fast
    # namespace_id = Column(ForeignKey('namespace.id', ondelete='CASCADE'),
    #         nullable=False, index=True)
    # namespace = relationship('Namespace', backref='threads')

    # only on messages from Gmail
    # NOTE: The same message sent to multiple users will be given a
    # different g_thrid for each user. We don't know yet if g_thrids are
    # unique globally.
    g_thrid = Column(String(255), nullable=True, index=True)

    def update_from_message(self, message):
        if message.internaldate > self.recentdate:
            self.recentdate = message.internaldate
        # subject is subject of original message in the thread
        if message.internaldate < self.recentdate:
            self.subject = message.subject
            self.subjectdate = message.internaldate
        message.thread = self
        return self

    @classmethod
    def from_message(cls, message, g_thrid):
        """
        Threads are broken solely on Gmail's X-GM-THRID for now. (Subjects
        are not taken into account, even if they change.)

        Returns the updated or new thread, and adds the message to the thread.
        Doesn't commit.
        """
        try:
            # NOTE: If g_thrid turns out to not be globally unique, we'll need
            # to join on Message and also filter by namespace here.
            thread = db_session.query(cls).filter_by(g_thrid=g_thrid).one()
            return thread.update_from_message(message)
        except NoResultFound:
            pass
        except MultipleResultsFound:
            log.info("Duplicate thread rows for thread {0}".format(g_thrid))
        thread = cls(subject=message.subject, g_thrid=g_thrid,
                recentdate=message.internaldate,
                subjectdate=message.internaldate)
        message.thread = thread
        return thread

    def cereal(self):
        """ Threads are serialized with full message data. """
        d = {}
        d['messages'] = [m.cereal() for m in self.messages]
        d['subject'] = self.subject
        d['recentdate'] = self.recentdate
        return d

class FolderSync(Base):
    __tablename__ = 'foldersync'

    id = Column(Integer, primary_key=True, autoincrement=True)

    imapaccount_id = Column(ForeignKey('imapaccount.id', ondelete='CASCADE'),
            nullable=False)
    imapaccount = relationship('IMAPAccount', backref='foldersyncs')
    # maximum Gmail label length is 225 (tested empirically), but constraining
    # folder_name uniquely requires max length of 767 bytes under utf8mb4
    # http://mathiasbynens.be/notes/mysql-utf8mb4
    folder_name = Column(String(191), nullable=False)

    # see state machine in sync.py
    state = Column(Enum('initial', 'initial uidinvalid',
                        'poll', 'poll uidinvalid', 'finish'),
                        default='initial', nullable=False)

    __table_args__ = (UniqueConstraint('imapaccount_id', 'folder_name'),)


config_prefix = 'RDS' if is_prod() else 'MYSQL'
database_name = config.get('_'.join([config_prefix, 'DATABASE']))

def db_uri():
    uri_template = 'mysql://{username}:{password}@{host}:{port}/{database}?charset=utf8mb4'
    config_prefix = 'RDS' if is_prod() else 'MYSQL'

    return uri_template.format(
        username = config.get('_'.join([config_prefix, 'USER'])),
        # http://stackoverflow.com/questions/15728290/sqlalchemy-valueerror-for-slash-in-password-for-create-engine (also applicable to '+' sign)
        password = urlquote(config.get('_'.join([config_prefix, 'PASSWORD']))),
        host = config.get('_'.join([config_prefix, 'HOSTNAME'])),
        port = config.get('_'.join([config_prefix, 'PORT'])),
        database = config.get('_'.join([config_prefix, 'DATABASE'])))

# My good old friend Enrico to the rescue:
# http://www.enricozini.org/2012/tips/sa-sqlmode-traditional/
#
# We set sql-mode=traditional on the server side as well, but enforce at the
# application level to be extra safe.
#
# Without this, MySQL will silently insert invalid values in the database if
# not running with sql-mode=traditional.
class ForceStrictMode(PoolListener):
    def connect(self, dbapi_con, connection_record):
        cur = dbapi_con.cursor()
        cur.execute("SET SESSION sql_mode='TRADITIONAL'")
        cur = None

engine = create_engine(db_uri(), listeners=[ForceStrictMode()])

def init_db():
    """ Make the tables. """
    Base.metadata.create_all(engine)

Session = sessionmaker()
Session.configure(bind=engine)

# A single global database session per Inbox instance is good enough for now.
db_session = Session()
