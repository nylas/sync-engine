from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()

# from sqlalchemy.ext.serializer import loads=, dumps
from sqlalchemy import event
from sqlalchemy.orm import reconstructor


class UserSession(Base):
    __tablename__ = 'user_sessions'

    session_token = Column(String, primary_key=True)
    email_address = Column(String)

    def __init__(self):
        self.session_token = None
        self.email_address  = None


class User(Base):
    __tablename__ = 'users'

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
    g_email = Column(String, primary_key=True)
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



import json
import postel
from bson import json_util



class MessageMeta(Base):
    __tablename__ = 'messages'

    _from_addr = Column(String)
    _sender_addr = Column(String)
    _reply_to = Column(String)
    _to_addr = Column(String)
    _cc_addr = Column(String)
    _bcc_addr = Column(String)
    _in_reply_to = Column(String)
    message_id = Column(String)
    date = Column(String)  # The date header
    subject = Column(String)
    internaldate = Column(DateTime)
    _flags = Column(String)
    uid = Column(String)

    g_msgid = Column(String, primary_key=True)
    g_thrid = Column(String)
    g_labels = Column(String)

    def __init__(self):
        self.from_addr = None
        self.sender_addr = None
        self.reply_to = None
        self.to_addr = None
        self.cc_addr = None
        self.bcc_addr = None
        self.in_reply_to = None
        self.message_id = None
        self.date = None
        self.internaldate = None
        self.g_msgid = None
        self.g_thrid = None
        self.g_labels = None
        self.flags = None
        self.subject = None
        self.uid = None  # TODO remove this



    @reconstructor
    def init_on_load(self):
        if self._from_addr: self.from_addr = json.loads(self._from_addr)
        if self._sender_addr: self.sender_addr = json.loads(self._sender_addr)
        if self._reply_to: self.reply_to = json.loads(self._reply_to)
        if self._to_addr: self.to_addr = json.loads(self._to_addr)
        if self._cc_addr: self.cc_addr = json.loads(self._cc_addr)
        if self._bcc_addr: self.bcc_addr = json.loads(self._bcc_addr)
        if self._in_reply_to: self.in_reply_to = json.loads(self._in_reply_to)
        if self._flags: self.flags = json.loads(self._flags)

    def gmail_url(self):
        if not self.uid:
            return
        return "https://mail.google.com/mail/u/0/#inbox/" + hex(self.uid)

    def trimmed_subject(self):
        s = self.subject
        if s[:4] == u'RE: ' or s[:4] == u'Re: ' :
            s = s[4:]
        return s


    def client_json(self):
        d = {}
        d['from'] = self.from_addr
        d['to'] = self.to_addr
        d['date'] = self.internaldate
        d['subject'] = self.subject
        return d

    def __repr__(self):
        return 'MessageMeta object: \n\t%s' % self.__dict__


@event.listens_for(MessageMeta, 'before_insert', propagate = True)
def serialize_before_insert(mapper, connection, target):
    if target.from_addr: target._from_addr = json.dumps(target.from_addr, default=json_util.default)
    if target.sender_addr: target._sender_addr = json.dumps(target.sender_addr, default=json_util.default)
    if target.reply_to: target._reply_to = json.dumps(target.reply_to, default=json_util.default)
    if target.to_addr: target._to_addr = json.dumps(target.to_addr, default=json_util.default)
    if target.cc_addr: target._cc_addr = json.dumps(target.cc_addr, default=json_util.default)
    if target.bcc_addr: target._bcc_addr = json.dumps(target.bcc_addr, default=json_util.default)
    if target.in_reply_to: target._in_reply_to = json.dumps(target.in_reply_to, default=json_util.default)
    if target.flags: target._flags = json.dumps(target.flags, default=json_util.default)




class MessagePart(Base):
    __tablename__ = 'parts'

    g_msgid = Column(String, ForeignKey(MessageMeta.g_msgid), primary_key=True)
    section = Column(String, primary_key=True)

    content_type = Column(String)
    charset = Column(String)
    bytes = Column(Integer)
    line_count = Column(Integer)
    filename = Column(String)

    s3_id = Column(String)
    host_id = Column(String)  # Which server holds onto this part


    def __init__(self):
        self.g_msgid = None
        self.section = None
        self.content_type = None
        self.charset = None
        self.bytes = None
        self.line_count = None
        self.filename = None
        self.s3_id = None
        self.host_id = None



    def __repr__(self):
        return '<IBMessagePart object> %s' % self.__dict__



## Make the tables

from sqlalchemy import create_engine

# engine = create_engine('sqlite:///:memory:', echo=True)

# sqlite://<nohostname>/<path>
# where <path> is relative:

# PATH_TO_DATABSE = os.path.join(os.path.dirname(os.path.realpath(__file__)), "database.db")
engine = create_engine('sqlite:///database.db')

Base.metadata.create_all(engine)

from sqlalchemy.orm import sessionmaker
Session = sessionmaker()
Session.configure(bind=engine)


db_session = Session()
