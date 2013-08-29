from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum
from sqlalchemy.types import PickleType

from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()

from sqlalchemy import event
from sqlalchemy.orm import reconstructor

from hashlib import sha256
import os
import logging as log

class JSONSerializable(object):
    def client_json(self):
        """ Override this and return a string of the object serialized for
            the web client.
        """
        pass


class UserSession(JSONSerializable, Base):
    __tablename__ = 'user_sessions'

    session_token = Column(String, primary_key=True)
    g_email = Column(String)

    def __init__(self):
        self.session_token = None
        self.email_address  = None


class User(JSONSerializable, Base):
    __tablename__ = 'users'

    g_email = Column(String, primary_key=True)

    # Not from google
    name = Column(String)
    date = Column(DateTime)

    g_token_issued_to = Column(String)
    g_user_id = Column(String)

    g_access_token = Column(String)
    g_id_token = Column(String)
    g_expires_in = Column(Integer)
    g_access_type = Column(String)
    g_token_type = Column(String)
    g_audience = Column(String)
    g_scope = Column(String)
    g_refresh_token = Column(String)
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
    # XXX clean this up a lot - make a better constructor, maybe taking
    # a mailbase as an argument to prefill a lot of attributes

    # TODO probably want to store some of these headers in a better
    # non-pickled way to provide indexing
    g_email = Column(String)
    from_addr = Column(PickleType)
    sender_addr = Column(PickleType)
    reply_to = Column(PickleType)
    to_addr = Column(PickleType)
    cc_addr = Column(PickleType)
    bcc_addr = Column(PickleType)
    in_reply_to = Column(PickleType)
    message_id = Column(String)
    subject = Column(String)
    internaldate = Column(DateTime)
    flags = Column(PickleType)
    size = Column(Integer)

    g_msgid = Column(String, primary_key=True)
    g_user_id = Column(String, primary_key=True)
    g_thrid = Column(String)

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
        self.flags = None
        self.subject = None
        self.g_user_id = None


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

    g_email = Column(String, primary_key=True)

    g_msgid = Column(String, primary_key=True)
    walk_index = Column(Integer, primary_key=True)
    # Save some space with common content types
    _content_type_common = Column(Enum(*common_content_types))
    _content_type_other = Column(String)

    content_disposition = Column(Enum('inline', 'attachment'))
    content_id = Column(String)  # For attachments
    size = Column(Integer)
    filename = Column(String)
    misc_keyval = Column(PickleType)
    s3_id = Column(String)
    data_sha256 = Column(String)

    def __init__(self):
        self.g_email = None
        self.g_msgid = None
        self.walk_index = None
        self.content_type = None
        self.content_disposition = None
        self.size = 0
        self.filename = None
        self.s3_id = None
        self.misc_keyval = None
        self.data_sha256 = None

    def __repr__(self):
        return 'MessagePart: %s' % self.__dict__


    def client_json(self):
        d = {}
        d['g_id'] = self.g_msgid
        d['g_index'] = self.walk_index
        d['content_type'] = self.content_type
        d['content_disposition'] = self.content_disposition
        d['size'] = self.size
        d['filename'] = self.filename
        return d

    @property
    def _data_file_directory(self):
        assert self.data_sha256
        # Nest it 6 items deep so we dont have huge folders
        h = str(self.data_sha256)
        return '../parts/'+ h[0]+'/'+h[1]+'/'+h[2]+'/'

    @property
    def _data_file_path(self):
        return self._data_file_directory + str(self.data_sha256)


    def set_data(self, new_data, write=True):
        # TODO handle deleting old values?
        # self.del_data()

        self.size = len(new_data)
        self.data_sha256 = sha256(new_data).hexdigest()

        if write:
            try: os.makedirs(self._data_file_directory)
            except: pass
            f = open(self._data_file_path, 'w')
            f.write(new_data)
            f.close()


    def get_data(self):
        pass
        f = open(self._data_file_path, 'r')
        return f.read()

    def del_data(self):
        pass
        try: os.remove(self._data_file_path)
        except: pass
        self.size = None
        self.data_sha256 = None

    data = property(get_data, set_data, del_data, "the message part payload")



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



class AttachmentParts(Base):
    __tablename__ = 'attachmentpart'
    """ These are objects which are attached to mail messages, but
        represented as links to external files
    """

    g_email = Column(String, primary_key=True)

    # This is a unique identifier that is used in the content URL
    content_id = Column(String, primary_key=True)  # For attachments

    content_type = Column(String)
    bytes = Column(Integer)
    filename = Column(String)
    _misc_keyval = Column(String)

    s3_id = Column(String)

    def __init__(self):
        self.g_email = None
        self.content_type = None
        self.bytes = None
        self.filename = None
        self.s3_id = None
        self.misc_keyval = None


class FolderMeta(JSONSerializable, Base):
    __tablename__ = 'foldermeta'
    """ This maps folder names to UIDs """

    g_email = Column(String)
    g_msgid = Column(String)
    folder_name = Column(String, primary_key=True)  # All Mail, Inbox, etc. (i.e. Labels)
    msg_uid = Column(String, primary_key=True)

class UIDValidity(JSONSerializable, Base):
    __tablename__ = 'uidvalidity'
    """ UIDValidity has a per-folder value. If it changes, we need to
        re-map g_msgid to UID for that folder.
    """
    g_email = Column(String, primary_key=True)
    folder_name = Column(String, primary_key=True)
    uid_validity = Column(Integer)
    highestmodseq = Column(Integer)

## Make the tables
from sqlalchemy import create_engine

# engine = create_engine('sqlite:///:memory:', echo=True)

# sqlite://<nohostname>/<path>
# where <path> is relative:

# PATH_TO_DATABSE = os.path.join(os.path.dirname(os.path.realpath(__file__)), "database.db")
# engine = create_engine('sqlite:///database.db', echo=True)
engine = create_engine('sqlite:///database.db')

Base.metadata.create_all(engine)

from sqlalchemy.orm import sessionmaker
Session = sessionmaker()
Session.configure(bind=engine)


db_session = Session()
