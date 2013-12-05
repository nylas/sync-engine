import os
import json

from hashlib import sha256
from itertools import chain

from sqlalchemy import Column, Integer, String, DateTime, Date, Boolean, Enum
from sqlalchemy import ForeignKey, Text, Index, func, event
from sqlalchemy import distinct
from sqlalchemy.orm import reconstructor, relationship, backref
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
Base = declarative_base()

from bs4 import BeautifulSoup, Doctype, Comment

from flanker import mime

from ..log import get_logger
log = get_logger()

from inbox.util.file import Lock
from inbox.util.html import plaintext2html
from inbox.util.misc import or_none, strip_plaintext_quote
from inbox.util.addr import parse_email_address

from .util import JSON, LittleJSON
from .revision import Revision
from .roles import JSONSerializable, Blob

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

    def total_stored_data(self, session):
        """ Computes the total size of the block data of emails in your
            account's IMAP folders
        """
        subq = session.query(Block) \
                .join(Block.message, Message.folderitems) \
                .filter(FolderItem.imapaccount_id==self.id) \
                .group_by(Message.id, Block.id)
        return session.query(func.sum(subq.subquery().columns.size)).scalar()

    def total_stored_messages(self, session):
        """ Computes the number of emails in your account's IMAP folders """
        return session.query(Message) \
                .join(Message.folderitems) \
                .filter(FolderItem.imapaccount_id==self.id) \
                .group_by(Message.id).count()

    def all_uids(self, session, folder_name):
        return [uid for uid, in
                session.query(FolderItem.msg_uid).filter_by(
                    imapaccount_id=self.id, folder_name=folder_name)]

    def g_msgids(self, session, in_=None):
        query = session.query(distinct(Message.g_msgid)).join(FolderItem) \
                    .filter(FolderItem.imapaccount_id==self.id)
        if in_:
            query = query.filter(Message.g_msgid.in_(in_))
        return sorted([g_msgid for g_msgid, in query], key=long)

    def g_metadata(self, session, folder_name):
        query = session.query(FolderItem.msg_uid, Message.g_msgid,
                    Message.g_thrid).filter(
                            FolderItem.imapaccount_id==self.id,
                            FolderItem.folder_name==folder_name,
                            FolderItem.message_id==Message.id)

        return dict([(int(uid), dict(msgid=g_msgid, thrid=g_thrid)) \
                for uid, g_msgid, g_thrid in query])

    def update_metadata(self, session, folder_name, uids, new_flags):
        """ Update flags (the only metadata that can change). """
        for item in session.query(FolderItem).filter(
                FolderItem.imapaccount_id==self.id,
                FolderItem.msg_uid.in_(uids),
                FolderItem.folder_name==folder_name):
            flags = new_flags[item.msg_uid]['flags']
            labels = new_flags[item.msg_uid]['labels']
            item.update_flags(flags, labels)
        session.commit()

    def remove_messages(self, session, uids, folder):
        fm_query = session.query(FolderItem).filter(
                FolderItem.imapaccount_id==self.id,
                FolderItem.folder_name==folder,
                FolderItem.msg_uid.in_(uids))
        fm_query.delete(synchronize_session='fetch')

        # not sure if this one is actually needed - does delete() automatically
        # commit?
        session.commit()

        # XXX TODO: Have a recurring worker permanently remove dangling
        # messages from the database and block store. (Probably too
        # expensive to do here.)

    def get_uidvalidity(self, session, folder_name):
        try:
            # using .one() here may catch duplication bugs
            return session.query(UIDValidity).filter_by(
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

    def create_message(self, folder_name, uid, internaldate, flags, body,
                       x_gm_thrid, x_gm_msgid, x_gm_labels):
        """ Parses message data, creates metadata database entries, computes
            threads, and writes mail parts to disk.

            Returns the new FolderItem, which links to new Message and Block
            objects through relationships. All new objects are uncommitted.

            Threads are not computed here; you gotta do that separately.
        """
        parsed = mime.from_string(body)

        mime_version = parsed.headers.get('Mime-Version')
        # NOTE: sometimes MIME-Version is set to "1.0 (1.0)", hence the
        # .startswith
        if mime_version is not None and not mime_version.startswith('1.0'):
            log.error("Unexpected MIME-Version: %s" % mime_version)

        new_msg = Message()
        new_msg.data_sha256 = sha256(body).hexdigest()
        # TODO: Detect which namespace to add message to.
        # Look up message thread,
        new_msg.namespace_id = self.namespace.id

        # clean_subject strips re:, fwd: etc.
        new_msg.subject = parsed.clean_subject
        new_msg.from_addr = parse_email_address(parsed.headers.get('From'))
        new_msg.sender_addr = parse_email_address(parsed.headers.get('Sender'))
        new_msg.reply_to = parse_email_address(parsed.headers.get('Reply-To'))
        new_msg.to_addr = or_none(parsed.headers.getall('To'),
                lambda tos: filter(lambda p: p is not None,
                    [parse_email_address(t) for t in tos]))
        new_msg.cc_addr = or_none(parsed.headers.getall('Cc'),
                lambda ccs: filter(lambda p: p is not None,
                    [parse_email_address(c) for c in ccs]))
        new_msg.bcc_addr = or_none(parsed.headers.getall('Bcc'),
                lambda bccs: filter(lambda p: p is not None,
                    [parse_email_address(c) for c in bccs]))
        new_msg.in_reply_to = parsed.headers.get('In-Reply-To')
        new_msg.message_id = parsed.headers.get('Message-Id')

        new_msg.internaldate = internaldate
        new_msg.g_msgid = x_gm_msgid
        new_msg.g_thrid = x_gm_thrid

        folder_item = FolderItem(imapaccount_id=self.id,
                folder_name=folder_name, msg_uid=uid, message=new_msg)
        folder_item.update_flags(flags, x_gm_labels)

        new_msg.size = len(body)  # includes headers text

        i = 0  # for walk_index

        # Store all message headers as object with index 0
        headers_part = Block()
        headers_part.message = new_msg
        headers_part.walk_index = i
        headers_part._data = json.dumps(parsed.headers.items())
        headers_part.size = len(headers_part._data)
        headers_part.data_sha256 = sha256(headers_part._data).hexdigest()
        new_msg.parts.append(headers_part)

        for mimepart in parsed.walk(
                with_self=parsed.content_type.is_singlepart()):
            i += 1
            if mimepart.content_type.is_multipart():
                log.warning("multipart sub-part found! on {0}".format(new_msg.g_msgid))
                continue  # TODO should we store relations?

            new_part = Block()
            new_part.message = new_msg
            new_part.walk_index = i
            new_part.misc_keyval = mimepart.headers.items()  # everything
            new_part.content_type = mimepart.content_type.value
            new_part.filename = mimepart.content_type.params.get('name')

            # Content-Disposition attachment; filename="floorplan.gif"
            if mimepart.content_disposition[0] is not None:
                value, params = mimepart.content_disposition
                if value not in ['inline', 'attachment']:
                    errmsg = """
Unknown Content-Disposition on message {0} found in {1}.
Bad Content-Disposition was: '{2}'
Parsed Content-Disposition was: '{3}'""".format(uid, folder_name,
        mimepart.content_disposition)
                    log.error(errmsg)
                    continue
                else:
                    new_part.content_disposition = value
                    if value == 'attachment':
                        new_part.filename = params.get('filename')

            if mimepart.body is None:
                data_to_write = ''
            elif new_part.content_type.startswith('text'):
                data_to_write = mimepart.body.encode('utf-8', 'strict')
            else:
                data_to_write = mimepart.body
            if data_to_write is None:
                data_to_write = ''
            # normalize mac/win/unix newlines
            data_to_write = data_to_write \
                    .replace('\r\n', '\n').replace('\r', '\n')

            new_part.content_id = mimepart.headers.get('Content-Id')

            new_part._data = data_to_write
            new_part.size = len(data_to_write)
            new_part.data_sha256 = sha256(data_to_write).hexdigest()
            new_msg.parts.append(new_part)
        new_msg.calculate_sanitized_body()

        return folder_item

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

    def threads_for_folder(self, session, folder_name):
        return session.query(Thread).join(Thread.messages).join(FolderItem) \
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

    from_addr = Column(JSON, nullable=True)
    sender_addr = Column(JSON, nullable=True)
    reply_to = Column(JSON, nullable=True)
    to_addr = Column(JSON, nullable=True)
    cc_addr = Column(JSON, nullable=True)
    bcc_addr = Column(JSON, nullable=True)
    in_reply_to = Column(JSON, nullable=True)
    message_id = Column(String(255), nullable=False)
    subject = Column(Text, nullable=True)
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
    g_thrid = Column(String(40), nullable=True)

    def calculate_sanitized_body(self):
        plain_part, html_part = self.body()
        snippet_length = 191
        if html_part:
            assert '\r' not in html_part, "newlines not normalized"

            # Try our best to strip out gmail quoted text.
            soup = BeautifulSoup(html_part.strip(), "lxml")
            for div in soup.findAll('div', 'gmail_quote'):
                div.extract()
            for container in soup.findAll('div', 'gmail_extra'):
                if container.contents is not None:
                    for tag in reversed(container.contents):
                        if not hasattr(tag, 'name') or tag.name != 'br': break
                        else: tag.extract()
                if container.contents is None:
                    # we emptied it!
                    container.extract()

            # Paragraphs don't need trailing line-breaks.
            for container in soup.findAll('p'):
                if container.contents is not None:
                    for tag in reversed(container.contents):
                        if not hasattr(tag, 'name') or tag.name != 'br': break
                        else: tag.extract()

            # Misc other crap.
            dtd = [item for item in soup.contents if isinstance(item, Doctype)]
            comments = soup.findAll(text=lambda text:isinstance(text, Comment))
            for tag in chain(dtd, comments):
                tag.extract()

            self.sanitized_body = unicode(soup)

            # trim for snippet
            for tag in soup.findAll(['style', 'head', 'title']):
                tag.extract()
            self.snippet = soup.get_text(' ')[:191]
        elif plain_part is None:
            self.sanitized_body = u''
            self.snippet = u''
        else:
            stripped = strip_plaintext_quote(plain_part.strip())
            self.sanitized_body = plaintext2html(stripped)
            self.snippet = stripped[:snippet_length]

    def body(self):
        """ Returns (plaintext, html) body for the message, decoded. """
        assert self.parts, \
                "Can't calculate body before parts have been parsed"

        plain_data = None
        html_data = None

        for part in self.parts:
            if part.content_type == 'text/html':
                html_data = part.get_data().decode('utf-8')
                break
        for part in self.parts:
            if part.content_type == 'text/plain':
                plain_data = part.get_data().decode('utf-8')
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

    ### Flags ###
    # Message has not completed composition (marked as a draft).
    is_draft = Column(Boolean, default=False, nullable=False)
    # Message has been read
    is_seen = Column(Boolean, default=False, nullable=False)
    # Message is "flagged" for urgent/special attention
    is_flagged = Column(Boolean, default=False, nullable=False)
    # session is the first session to have been notified about this message
    is_recent = Column(Boolean, default=False, nullable=False)
    # Message has been answered
    is_answered = Column(Boolean, default=False, nullable=False)
    # things like: ['$Forwarded', 'nonjunk', 'Junk']
    extra_flags = Column(LittleJSON, nullable=False)

    def update_flags(self, new_flags, x_gm_labels=None):
        new_flags = set(new_flags)
        col_for_flag = {
                u'\\Draft': 'is_draft',
                u'\\Seen': 'is_seen',
                u'\\Recent': 'is_recent',
                u'\\Answered': 'is_answered',
                u'\\Flagged': 'is_flagged',
                }
        for flag, col in col_for_flag.iteritems():
            setattr(self, col, flag in new_flags)
            new_flags.discard(flag)
        # Gmail doesn't use the \Draft flag. Go figure.
        if '\\Draft' in x_gm_labels:
            self.is_draft = True
        self.extra_flags = sorted(new_flags)

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

    subject = Column(Text, nullable=True)
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
    def from_message(cls, session, message, g_thrid):
        """
        Threads are broken solely on Gmail's X-GM-THRID for now. (Subjects
        are not taken into account, even if they change.)

        Returns the updated or new thread, and adds the message to the thread.
        Doesn't commit.
        """
        try:
            # NOTE: If g_thrid turns out to not be globally unique, we'll need
            # to join on Message and also filter by namespace here.
            thread = session.query(cls).filter_by(g_thrid=g_thrid).one()
            return thread.update_from_message(message)
        except NoResultFound:
            pass
        except MultipleResultsFound:
            log.info("Duplicate thread rows for thread {0}".format(g_thrid))
            raise
        thread = cls(subject=message.subject, g_thrid=g_thrid,
                recentdate=message.internaldate,
                subjectdate=message.internaldate)
        message.thread = thread
        return thread

    def cereal(self):
        """ Threads are serialized with full message data. """
        d = {}
        d['id'] = self.id
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

class Transaction(Base, Revision):
    """ Transactional log to enable client syncing. """
    __tablename__ = 'transaction'

    namespace_id = Column(Integer, ForeignKey('namespace.id'), nullable=False,
            unique=True)
    namespace = relationship('Namespace',
            backref=backref('namespace', uselist=False))
