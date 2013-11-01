import os

from sqlalchemy import Column, Integer, String, DateTime, Date, Boolean, Enum
from sqlalchemy import create_engine, ForeignKey, Text, Index, func, event
from sqlalchemy import distinct
from sqlalchemy.types import PickleType
from sqlalchemy.orm import reconstructor, relationship, backref, sessionmaker
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()

from hashlib import sha256

from sqlalchemy.dialects import mysql
from boto.s3.connection import S3Connection
from boto.s3.key import Key

from ..util.file import mkdirp, remove_file, Lock
from .config import config, is_prod
from .log import get_logger
log = get_logger()

from urllib import quote_plus as urlquote

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
    data_sha256 = Column(String(255))
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
            # NOTE: This is a placeholder for "empty bytes". If this doesn't
            # work as intended, it will trigger the hash assertion later.
            data = ""
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

class MediumPickle(PickleType):
    impl = mysql.MEDIUMBLOB

### Tables

# global

class IMAPAccount(Base):
    __tablename__ = 'imapaccount'
    id = Column(Integer, primary_key=True, autoincrement=True)
    # user_id refers to Inbox's user id
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    user = relationship("User", backref="accounts")

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
                    imapaccount_id=self.account_id,
                    folder_name=folder_name)]

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
            if fm.flags != new_flags[fm.msg_uid]:
                fm.flags = new_flags[fm.msg_uid]
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

class UserSession(Base):
    """ Inbox-specific sessions. """
    __tablename__ = 'user_session'

    id = Column(Integer, primary_key=True, autoincrement=True)

    token = Column(String(40))
    # sessions have a many-to-one relationship with users
    user_id = Column(Integer, ForeignKey('user.id'),
            nullable=False)
    user = relationship('User', backref='sessions')

class Namespace(Base):
    """ A way to do grouping / permissions, basically. """
    __tablename__ = 'namespace'
    id = Column(Integer, primary_key=True, autoincrement=True)
    # NOTE: only root namespaces have IMAP accounts
    # http://stackoverflow.com/questions/386294/what-is-the-maximum-length-of-a-valid-email-address
    imapaccount_id = Column(Integer, ForeignKey('imapaccount.id'),
            nullable=True)
    imapaccount = relationship('IMAPAccount', backref=backref('namespace',
        uselist=False)) # really the root_namespace
    # TODO should have a name that defaults to gmail

    # invariant: imapaccount is non-null iff namespace_type is root
    namespace_type = Column(Enum('root', 'shared_folder', 'todo'), nullable=False, default='root')

    @property
    def email_address(self):
        if self.imapaccount is not None:
            return self.imapaccount.email_address

    @property
    def is_root(self):
        return self.imapaccount_id is not None

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

    imapaccount_id = Column(ForeignKey('imapaccount.id'), nullable=False)
    imapaccount = relationship("IMAPAccount")

    g_id = Column(String(64))
    source = Column("source", Enum("local", "remote"))

    email_address = Column(String(254), nullable=True, index=True)
    name = Column(Text(collation='utf8_unicode_ci'))
    # phone_number = Column(String(64))

    updated_at = Column(DateTime, default=func.now(), onupdate=func.current_timestamp())
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (UniqueConstraint('g_id', 'source',
        'imapaccount_id', name='_contact_uc'),)

    def cereal(self):
        return dict(id=self.id,
                    email=self.email_address,
                    name=self.name)

    def __repr__(self):
        return str(self.name) + ", " + str(self.email) + ", " + str(self.source)

# sharded (by namespace)

class Message(JSONSerializable, Base):
    __tablename__ = 'message'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # XXX clean this up a lot - make a better constructor, maybe taking
    # a mailbase as an argument to prefill a lot of attributes

    namespace_id = Column(ForeignKey('namespace.id'), nullable=False)
    namespace = relationship("Namespace", backref="messages",
            order_by=lambda msg: msg.internaldate)

    thread_id = Column(Integer, ForeignKey('thread.id'), nullable=False)
    thread = relationship('Thread', backref="messages",
            order_by=lambda msg: msg.internaldate)

    # TODO probably want to store some of these headers in a better
    # non-pickled way to provide indexing
    from_addr = Column(MediumPickle)
    sender_addr = Column(MediumPickle)
    reply_to = Column(MediumPickle)
    to_addr = Column(MediumPickle)
    cc_addr = Column(MediumPickle)
    bcc_addr = Column(MediumPickle)
    in_reply_to = Column(MediumPickle)
    message_id = Column(String(255))
    subject = Column(Text(collation='utf8_unicode_ci'))
    internaldate = Column(DateTime)
    size = Column(Integer, default=0)
    data_sha256 = Column(String(255))

    # only on messages from Gmail
    g_msgid = Column(String(255), nullable=True)

    def trimmed_subject(self):
        s = self.subject
        if s[:4] == u'RE: ' or s[:4] == u'Re: ' :
            s = s[4:]
        return s

    def cereal(self):
        # TODO serialize more here for client API
        d = {}
        d['from'] = self.from_addr
        d['to'] = self.to_addr
        d['date'] = self.internaldate
        d['subject'] = self.subject
        d['id'] = self.id
        d['g_thrid'] = self.g_thrid
        d['namespace_id'] = self.namespace_id
        return d

# make pulling up all messages in a given thread fast
Index('message_namespace_id_g_thrid', Message.namespace_id,
        Message.g_thrid)

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
    __tablename__ = 'blockmeta'
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
    misc_keyval = Column(MediumPickle)

    is_inboxapp_attachment = Column(Boolean, default=False)
    collection_id = Column(Integer, ForeignKey("collections.id"), nullable=True)
    collection = relationship('Collection', backref="parts")

    # TODO: create a constructor that allows the 'content_type' keyword

    __table_args__ = (UniqueConstraint('message_id', 'walk_index',
        'data_sha256', name='_blockmeta_uc'),)

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

    imapaccount_id = Column(ForeignKey('imapaccount.id'), nullable=False)
    imapaccount = relationship("IMAPAccount")
    message_id = Column(Integer, ForeignKey('message.id'), nullable=False)
    message = relationship('Message')
    msg_uid = Column(Integer, nullable=False)
    folder_name = Column(String(255), nullable=False)  # All Mail, Inbox, etc. (i.e. Labels)
    flags = Column(MediumPickle)

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
    account_id = Column(ForeignKey('imapaccount.id'), nullable=False)
    account = relationship("IMAPAccount")
    folder_name = Column(String(255))
    uid_validity = Column(Integer)
    highestmodseq = Column(Integer)

    __table_args__ = (UniqueConstraint('account_id', 'folder_name',
        name='_folder_account_uc'),)

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

    # TODO change this to a ForeignKey constraint once threads are represented
    # as database objects (and then rename to remove the "g_")
    g_thrid = Column(String(255), nullable=False)

    # Gmail thread IDs are only unique per-account, so in order to de-dupe, we
    # need to store the account that this thread came from. When we get a
    # Thread database table, these two lines can go.
    imapaccount_id = Column(ForeignKey('imapaccount.id'), nullable=False)
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
            )

class TodoNamespace(Base):
    __tablename__ = 'todonamespace'
    """ A 1-1 mapping between users and their todo namespaces """

    id = Column(Integer, primary_key=True, autoincrement=True)

    namespace = relationship('Namespace', backref=backref('todo_namespace', uselist=False))
    namespace_id = Column(Integer, ForeignKey('namespace.id'), nullable=False, unique=True)

    user = relationship('User', backref=backref('todo_namespace', uselist=False))
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False, unique=True)

class Thread(Base):
    """ Pre-computed thread metadata.

    (We have all this information elsewhere, but it's not as nice to use.)
    """
    __tablename__ = 'thread'

    id = Column(Integer, primary_key=True, autoincrement=True)

    subject = Column(Text(collation='utf8_unicode_ci'))

    # only on messages from Gmail
    g_thrid = Column(String(255), nullable=True)

class SyncMeta(Base):
    __tablename__ = 'syncmeta'

    id = Column(Integer, primary_key=True, autoincrement=True)

    imapaccount_id = Column(ForeignKey('imapaccount.id'), nullable=False)
    imapaccount = relationship('IMAPAccount',
            backref=backref('syncmeta', uselist=False))
    folder_name = Column(String(255))

    # see state machine in sync.py
    state = Column(Enum('initial', 'initial uidinvalid',
                        'poll', 'poll uidinvalid'),
                        default='initial', nullable=False)

    __table_args__ = (UniqueConstraint('imapaccount_id', 'folder_name'),)

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

engine = create_engine(db_uri())

def init_db():
    """ Make the tables. """
    Base.metadata.create_all(engine)

Session = sessionmaker()
Session.configure(bind=engine)

# A single global database session per Inbox instance is good enough for now.
db_session = Session()
