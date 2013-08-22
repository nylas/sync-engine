from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()

from sqlalchemy import event
from sqlalchemy.orm import reconstructor

# from sqlalchemy.ext.serializer import loads=, dumps
import json
from bson import json_util


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
    g_allmail_uidvalidity = Column(Integer)

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



class MessageMeta(Base):
    __tablename__ = 'messagemeta'
    # XXX clean this up a lot - make a better constructor, maybe taking
    # a mailbase as an argument to prefill a lot of attributes

    in_inbox = Column(Boolean)

    _from_addr = Column(String)
    _sender_addr = Column(String)
    _reply_to = Column(String)
    _to_addr = Column(String)
    _cc_addr = Column(String)
    _bcc_addr = Column(String)
    _in_reply_to = Column(String)
    message_id = Column(String)
    subject = Column(String)
    internaldate = Column(DateTime)
    _flags = Column(String)


    uid = Column(String)  # This is only for all_mail

    g_msgid = Column(String, primary_key=True)
    g_user_id = Column(String, ForeignKey(User.g_user_id), primary_key=True)

    g_thrid = Column(String)
    g_labels = Column(String)

    def __init__(self):
        self.in_inbox = None
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
        self.g_user_id = None


    @reconstructor
    def init_on_load(self):

        def d(name):  # deseralize
            try:
                if self.__dict__['_'+name]:
                    self.__dict__[name] = json.loads(self.__dict__['_'+name])
                else:
                    self.__dict__[name] = None
            except KeyError, e:
                # Deferred
                pass

        names = ['from_addr',
                'sender_addr',
                'reply_to',
                'to_addr',
                'cc_addr',
                'bcc_addr',
                'in_reply_to',
                'flags']
        for n in names: d(n)



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
        # TODO serialize more here for client API
        d = {}
        d['from'] = self.from_addr
        d['to'] = self.to_addr
        d['date'] = self.internaldate
        d['subject'] = self.subject
        d['data_id'] = self.g_msgid
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
    __tablename__ = 'messagepart'
    """ Metadata for message parts stored in s3 """

    g_msgid = Column(String, ForeignKey(MessageMeta.g_msgid), primary_key=True)
    section = Column(String, primary_key=True)
    encoding = Column(String)
    content_type = Column(String)
    charset = Column(String)
    bytes = Column(Integer)
    line_count = Column(Integer)
    filename = Column(String)
    _misc_keyval = Column(String)
    allmail_uid = Column(String, primary_key=True)

    s3_id = Column(String)
    host_id = Column(String)  # Which server holds onto this part


    def __init__(self):
        self.g_msgid = None
        self.section = None
        self.content_type = None
        self.encoding = None
        self.charset = None
        self.bytes = None
        self.line_count = None
        self.filename = None
        self.s3_id = None
        self.host_id = None
        self.misc_keyval = None
        self.allmail_uid = None

    def __repr__(self):
        return 'MessagePart: %s' % self.__dict__

    @reconstructor
    def init_on_load(self):
        if self._misc_keyval: self.misc_keyval = json.loads(self._misc_keyval)


@event.listens_for(MessagePart, 'before_insert', propagate = True)
def serialize_before_insert(mapper, connection, target):
    if target.misc_keyval: target._misc_keyval = json.dumps(target.misc_keyval, default=json_util.default)




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
