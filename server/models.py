import os

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum, Text
from sqlalchemy import ForeignKey
from sqlalchemy.types import PickleType

from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()

from sqlalchemy import event
from sqlalchemy.orm import reconstructor, relationship
from sqlalchemy.schema import UniqueConstraint

from hashlib import sha256
from os import environ
from server.util import mkdirp

import logging as log
# from sqlalchemy.databases.mysql import MSMediumBlob
from sqlalchemy.dialects import mysql
from boto.s3.connection import S3Connection
from boto.s3.key import Key

class JSONSerializable(object):
    def client_json(self):
        """ Override this and return a string of the object serialized for
            the web client.
        """
        pass

STORE_MSG_ON_S3 = False

class MediumPickle(PickleType):
    impl = mysql.MEDIUMBLOB


class UserSession(JSONSerializable, Base):
    __tablename__ = 'user_sessions'

    id = Column(Integer, primary_key=True, autoincrement=True)

    session_token = Column(String(255))
    g_email = Column(String(255))

    def __init__(self):
        self.session_token = None
        self.email_address  = None


class User(JSONSerializable, Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)

    g_email = Column(String(255), unique=True)  # Should add index=true?

    # Not from google
    name = Column(String(255))
    date = Column(DateTime)
    # extra flags
    initial_sync_done = Column(Boolean)

    g_token_issued_to = Column(String(512))
    g_user_id = Column(String(512))

    # TODO figure out the actual lengths of these
    g_access_token = Column(String(1024))
    g_id_token = Column(String(1024))
    g_expires_in = Column(Integer)
    g_access_type = Column(String(512))
    g_token_type = Column(String(512))
    g_audience = Column(String(512))
    g_scope = Column(String(512))
    g_refresh_token = Column(String(512))
    g_verified_email = Column(Boolean)

    def __init__(self):
        self.name = None

        self.g_token_issued_to = None
        self.g_user_id = None

        self.g_access_token =None
        self.g_id_token = None
        self.g_expires_in = None
        self.g_access_type = None
        self.g_token_type = None
        self.g_audience = None
        self.date = None
        self.g_scope = None
        self.g_email = None
        self.g_refresh_token = None
        self.g_verified_email = None
        self.g_allmail_uidvalidity = None



class MessageMeta(JSONSerializable, Base):
    __tablename__ = 'messagemeta'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # XXX clean this up a lot - make a better constructor, maybe taking
    # a mailbase as an argument to prefill a lot of attributes

    # TODO probably want to store some of these headers in a better
    # non-pickled way to provide indexing
    g_email = Column(String(255))
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
    size = Column(Integer)
    data_sha256 = Column(String(255))
    g_msgid = Column(String(255), primary_key=True)
    g_user_id = Column(String(255), primary_key=True)
    g_thrid = Column(String(255))

    def __init__(self):
        self.g_email = None
        self.from_addr = None
        self.sender_addr = None
        self.reply_to = None
        self.to_addr = None
        self.cc_addr = None
        self.bcc_addr = None
        self.in_reply_to = None
        self.message_id = None
        self.date = None
        self.size = 0
        self.internaldate = None
        self.g_msgid = None
        self.g_thrid = None
        self.subject = None
        self.g_user_id = None
        self.data_sha256 = None


    # def gmail_url(self):
    #     if not self.uid:
    #         return
    #     return "https://mail.google.com/mail/u/0/#inbox/" + hex(self.uid)


    def trimmed_subject(self):
        s = self.subject
        if s[:4] == u'RE: ' or s[:4] == u'Re: ' :
            s = s[4:]
        return s


    def client_json(self):
        # TODO serialize more here for client API
        d = {}
        d['from'] = self.from_addr
        d['to'] = self.to_addr
        d['date'] = self.internaldate
        d['subject'] = self.subject
        d['g_id'] = self.g_msgid
        d['g_thrid'] = self.g_thrid
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


class MessagePart(JSONSerializable, Base):
    __tablename__ = 'messagepart'
    """ Metadata for message parts stored in s3 """

    id = Column(Integer, primary_key=True, autoincrement=True)
    messagemeta_id = Column(Integer, ForeignKey('messagemeta.id'), nullable=False)
    messagemeta = relationship('MessageMeta', backref="parts")

    walk_index = Column(Integer)
    # Save some space with common content types
    _content_type_common = Column(Enum(*common_content_types))
    _content_type_other = Column(String(255))
    filename = Column(String(255))

    content_disposition = Column(Enum('inline', 'attachment'))
    content_id = Column(String(255))  # For attachments
    size = Column(Integer, default=0)
    misc_keyval = Column(MediumPickle)
    s3_id = Column(String(255))
    data_sha256 = Column(String(255))

    is_inboxapp_attachment = Column(Boolean, default=False)

    __table_args__ = (UniqueConstraint('messagemeta_id', 'walk_index', 'data_sha256',
        name='_messagepart_uc'),)

    def __init__(self, *args, **kwargs):
        self.content_type = None
        self.size = 0
        Base.__init__(self, *args, **kwargs)

    def __repr__(self):
        return 'MessagePart: %s' % self.__dict__

    def client_json(self):
        d = {}
        d['g_id'] = self.messagemeta.g_msgid
        d['g_index'] = self.walk_index
        d['content_type'] = self.content_type
        d['content_disposition'] = self.content_disposition
        d['size'] = self.size
        d['filename'] = self.filename
        return d

    def save(self, data):
        assert data is not None, \
                "MessagePart can't have NoneType body (can be zero-length, though!)"
        self.size = len(data)
        self.data_sha256 = sha256(data).hexdigest()
        if STORE_MSG_ON_S3:
            self._save_to_s3(data)
        else:
            self._save_to_disk(data)

    def get_data(self):
        # NOTE: if we were to optimize out fetching blank MIME parts, it would
        # go here.
        if STORE_MSG_ON_S3:
            data = self._get_from_s3()
        else:
            data = self._get_from_disk()
        assert self.data_sha256 == sha256(data).hexdigest(), "Returned data doesn't match stored hash!"
        return data

    def delete_data(self):
        if STORE_MSG_ON_S3:
            self._delete_from_s3()
        else:
            self._delete_from_disk()
        # TODO should we clear these fields?
        # self.size = None
        # self.data_sha256 = None

    def _save_to_s3(self, data):
        assert len(data) > 0, "Need data to save!"
        assert 'AWS_ACCESS_KEY_ID' in environ, "Need AWS key!"
        assert 'AWS_SECRET_ACCESS_KEY' in environ, "Need AWS secret!"
        assert 'MESSAGE_STORE_BUCKET_NAME' in environ, "Need bucket name to store message data!"
        # Boto pools connections at the class level
        conn = S3Connection(environ.get('AWS_ACCESS_KEY_ID'),
                            environ.get('AWS_SECRET_ACCESS_KEY'))
        bucket = conn.get_bucket(environ.get('MESSAGE_STORE_BUCKET_NAME'))

        # See if it alreays exists and has the same hash
        data_obj = bucket.get_key(self.data_sha256)
        if data_obj:
            assert data_obj.get_metadata('data_sha256') == self.data_sha256, \
                "MessagePart hash doesn't match what we previously stored on s3 !"
            log.info("MessagePart already exists on S3.")
            return

        data_obj = Key(bucket)
        # if metadata:
        #     assert type(metadata) is dict
        #     for k, v in metadata.iteritems():
        #         data_obj.set_metadata(k, v)
        data_obj.set_metadata('data_sha256', self.data_sha256)
        # data_obj.content_type = self.content_type  # Experimental
        data_obj.key = self.data_sha256
        log.info("Writing data to S3 with hash %s" % self.data_sha256)
        # def progress(done, total):
        #     log.info("%.2f%% done" % (done/total * 100) )
        # data_obj.set_contents_from_string(data, cb=progress)
        data_obj.set_contents_from_string(data)


    def _get_from_s3(self):
        assert self.data_sha256
        # Boto pools connections at the class level
        conn = S3Connection(environ.get('AWS_ACCESS_KEY_ID'),
                            environ.get('AWS_SECRET_ACCESS_KEY'))
        bucket = conn.get_bucket(environ.get('MESSAGE_STORE_BUCKET_NAME'))
        data_obj = bucket.get_key(self.data_sha256)
        assert data_obj
        return bucket.get_contents_as_string(data_obj)


    def _delete_from_s3(self):
        # TODO
        pass


    # Helpers
    @property
    def _data_file_directory(self):
        assert self.data_sha256
        # Nest it 6 items deep so we dont have folders with too many files
        h = str(self.data_sha256)
        return '../parts/'+ h[0]+'/'+h[1]+'/'+h[2]+'/'+h[3]+'/'+h[4]+'/'+h[5]+'/'

    @property
    def _data_file_path(self):
        return self._data_file_directory + str(self.data_sha256)


    def _save_to_disk(self, data):
        mkdirp(self._data_file_directory)
        f = open(self._data_file_path, 'w')
        f.write(data)
        f.close()

    def _get_from_disk(self):
        try:
            f = open(self._data_file_path, 'r')
            return f.read()
        except Exception:
            log.error("No data for hash %s" % self.data_sha256)
            return None

    def _delete_from_disk(self):
        try: os.remove(self._data_file_path)
        except: pass

    @reconstructor
    def init_on_load(self):
        if self._content_type_common:
            self.content_type = self._content_type_common
        else:
            self.content_type = self._content_type_other

@event.listens_for(MessagePart, 'before_insert', propagate = True)
def serialize_before_insert(mapper, connection, target):
    if target.content_type in common_content_types:
        target._content_type_common = target.content_type
        target._content_type_other = None
    else:
        target._content_type_common = None
        target._content_type_other = target.content_type

class FolderMeta(JSONSerializable, Base):
    __tablename__ = 'foldermeta'
    """ This maps folder names to UIDs """

    id = Column(Integer, primary_key=True, autoincrement=True)

    # XXX ForeignKey into Users table instead?
    g_email = Column(String(255))
    # XXX ForeignKey into MessageMeta table instead?
    g_msgid = Column(String(255))
    msg_uid = Column(String(255))
    folder_name = Column(String(255))  # All Mail, Inbox, etc. (i.e. Labels)
    flags = Column(MediumPickle)

    __table_args__ = (UniqueConstraint('folder_name', 'msg_uid', 'g_email',
        name='_folder_msg_email_uc'),)

class UIDValidity(JSONSerializable, Base):
    __tablename__ = 'uidvalidity'
    """ UIDValidity has a per-folder value. If it changes, we need to
        re-map g_msgid to UID for that folder.
    """

    id = Column(Integer, primary_key=True, autoincrement=True)
    g_email = Column(String(255))  # Should add index=true?
    folder_name = Column(String(255))
    uid_validity = Column(Integer)
    highestmodseq = Column(Integer)

    __table_args__ = (UniqueConstraint('g_email', 'folder_name',
        name='_folder_email_uc'),)




## Make the tables
from sqlalchemy import create_engine
DB_URI = "mysql://{username}:{password}@{host}:{port}/{database}?charset=utf8mb4"

if 'RDS_HOSTNAME' in environ:
    # Amazon RDS settings for production
    engine = create_engine(DB_URI.format(
        username = environ.get('RDS_USER'),
        password = environ.get('RDS_PASSWORD'),
        host = environ.get('RDS_HOSTNAME'),
        port = environ.get('RDS_PORT'),
        database = environ.get('RDS_DB_NAME')
    ))

else:

    if os.environ['MYSQL_USER'] == 'XXXXXXX':
        log.error("Go setup MySQL settings in config file!")
        raise Exception()

    engine = create_engine(DB_URI.format(
        username = environ.get('MYSQL_USER'),
        password = environ.get('MYSQL_PASSWORD'),
        host = environ.get('MYSQL_HOSTNAME'),
        port = environ.get('MYSQL_PORT'),
        database = environ.get('MYSQL_DATABASE')
    ))


# ## Make the tables
# from sqlalchemy import create_engine
# DB_URI = "mysql+pymysql://{username}:{password}@{host}:{port}/{database}"


# if 'RDS_HOSTNAME' in environ:
#     # Amazon RDS settings for production
#     engine = create_engine(DB_URI.format(
#         username = environ.get('RDS_USER'),
#         password = environ.get('RDS_PASSWORD'),
#         host = environ.get('RDS_HOSTNAME'),
#         port = environ.get('RDS_PORT'),
#         database = environ.get('RDS_DB_NAME')
#     ), connect_args = {'charset': 'utf8mb4'} )

# else:

#     if os.environ['MYSQL_USER'] == 'XXXXXXX':
#         log.error("Go setup MySQL settings in config file!")
#         raise Exception()

#     engine = create_engine(DB_URI.format(
#         username = environ.get('MYSQL_USER'),
#         password = environ.get('MYSQL_PASSWORD'),
#         host = environ.get('MYSQL_HOSTNAME'),
#         port = environ.get('MYSQL_PORT'),
#         database = environ.get('MYSQL_DATABASE')
#     ), connect_args = {'charset': 'utf8mb4'} )





Base.metadata.create_all(engine)

from sqlalchemy.orm import sessionmaker
Session = sessionmaker()
Session.configure(bind=engine)


db_session = Session()
