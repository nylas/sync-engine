import itertools
import os
import sys
import re
import json
import traceback

from itertools import chain
from hashlib import sha256
from datetime import datetime

from sqlalchemy import (Column, Integer, BigInteger, String, DateTime, Boolean,
                        Enum, ForeignKey, Text, func, event, and_, or_, asc)
from sqlalchemy.orm import (reconstructor, relationship, backref, deferred,
                            validates, object_session)
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.types import BLOB
from sqlalchemy.sql.expression import true, false

from bs4 import BeautifulSoup, Doctype, Comment

from inbox.server.log import get_logger
log = get_logger()

from inbox.server.config import config

from inbox.util.file import Lock, mkdirp
from inbox.util.html import plaintext2html
from inbox.util.misc import strip_plaintext_quote, load_modules
from inbox.util.cryptography import encrypt_aes, decrypt_aes
from inbox.sqlalchemy.util import (JSON, Base36UID, generate_public_id,
                                   maybe_refine_query)
from inbox.sqlalchemy.revision import Revision, gen_rev_role
from inbox.server.basicauth import AUTH_TYPES

from inbox.server.models.roles import Blob
from inbox.server.models import Base


def register_backends():
    import inbox.server.models.tables

    # Find and import
    modules = load_modules(inbox.server.models.tables)

    # Create mapping
    table_mod_for = {}
    for module in modules:
        if hasattr(module, 'PROVIDER'):
            provider = module.PROVIDER
            table_mod_for[provider] = module

    return table_mod_for


class HasPublicID(object):
    public_id = Column(Base36UID, nullable=False,
                       index=True, default=generate_public_id)


# global
class Account(Base, HasPublicID):
    # user_id refers to Inbox's user id
    user_id = Column(Integer, ForeignKey('user.id', ondelete='CASCADE'),
                     nullable=False)
    user = relationship('User', backref='accounts')

    # http://stackoverflow.com/questions/386294/what-is-the-maximum-length-of-a-valid-email-address
    email_address = Column(String(254), nullable=True, index=True)
    provider = Column(Enum('Gmail', 'Outlook', 'Yahoo', 'EAS', 'Inbox'),
                      nullable=False)

    # local flags & data
    save_raw_messages = Column(Boolean, server_default=true())

    sync_host = Column(String(255), nullable=True)
    last_synced_contacts = Column(DateTime, nullable=True)

    # 'Required' folder name mappings for the Inbox datastore API
    inbox_folder_name = Column(String(255), nullable=True)
    drafts_folder_name = Column(String(255), nullable=True)
    # NOTE: Spam, Trash might be added later

    # Optional folder name mappings
    archive_folder_name = Column(String(255), nullable=True)
    sent_folder_name = Column(String(255), nullable=True)

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

    # Password stuff
    # 'deferred' loads these large binary fields into memory only when needed
    # i.e. on direct access.
    password_aes = deferred(Column(BLOB(256)))
    key = deferred(Column(BLOB(128)))

    @classmethod
    def _get_lock_object(cls, account_id, lock_for=dict()):
        """ Make sure we only create one lock per account per process.

        (Default args are initialized at import time, so `lock_for` acts as a
        module-level memory cache.)
        """
        return lock_for.setdefault(account_id,
                                   Lock(cls._sync_lockfile_name(account_id),
                                        block=False))

    @classmethod
    def _sync_lockfile_name(cls, account_id):
        return "/var/lock/inbox_sync/{}.lock".format(account_id)

    @property
    def _sync_lock(self):
        return self._get_lock_object(self.id)

    def sync_lock(self):
        """ Prevent mailsync for this account from running more than once. """
        self._sync_lock.acquire()

    def sync_unlock(self):
        self._sync_lock.release()

    @property
    def password(self):
        if self.password_aes is not None:
            with open(self._keyfile, 'r') as f:
                key = f.read()

            key = self.key + key
            return decrypt_aes(self.password_aes, key)

    @password.setter
    def password(self, value):
        assert AUTH_TYPES.get(self.provider) == 'Password'
        assert value is not None

        key_size = int(config.get('KEY_SIZE', 128))
        self.password_aes, key = encrypt_aes(value, key_size)
        self.key = key[:len(key) / 2]

        with open(self._keyfile, 'w+') as f:
            f.write(key[len(key) / 2:])

    @property
    def _keyfile(self, create_dir=True):
        assert self.key

        key_dir = config.get('KEY_DIR', None)
        assert key_dir
        if create_dir:
            mkdirp(key_dir)
        key_filename = '{0}'.format(sha256(self.key).hexdigest())
        return os.path.join(key_dir, key_filename)

    discriminator = Column('type', String(16))
    __mapper_args__ = {'polymorphic_on': discriminator,
                       'polymorphic_identity': 'account'}


class UserSession(Base, HasPublicID):
    """ Inbox-specific sessions. """
    token = Column(String(40))

    user_id = Column(Integer, ForeignKey('user.id', ondelete='CASCADE'),
                     nullable=False)
    user = relationship('User', backref='sessions')


class Namespace(Base, HasPublicID):
    """ A way to do grouping / permissions, basically. """
    # NOTE: only root namespaces have IMAP accounts
    account_id = Column(Integer,
                        ForeignKey('account.id', ondelete='CASCADE'),
                        nullable=True)
    # really the root_namespace
    account = relationship('Account',
                           backref=backref('namespace', uselist=False))

    # invariant: imapaccount is non-null iff type is root
    type = Column(Enum('root', 'shared_folder'), nullable=False,
                  server_default='root')

    @property
    def email_address(self):
        if self.account is not None:
            return self.account.email_address


class SharedFolder(Base, HasPublicID):
    # Don't delete shared folders if the user that created them is deleted.
    user_id = Column(Integer, ForeignKey('user.id', ondelete='SET NULL'),
                     nullable=True)
    user = relationship('User', backref='sharedfolders')

    namespace = relationship('Namespace', backref='sharedfolders')
    # Do delete shared folders if their associated namespace is deleted.
    namespace_id = Column(Integer, ForeignKey(
        'namespace.id', ondelete='CASCADE'), nullable=False)

    display_name = Column(String(40))


class User(Base, HasPublicID):
    name = Column(String(255))

# sharded (by namespace)


class Transaction(Base, Revision):
    """ Transactional log to enable client syncing. """
    # Do delete transactions if their associated namespace is deleted.
    namespace_id = Column(Integer,
                          ForeignKey('namespace.id', ondelete='CASCADE'),
                          nullable=False)
    namespace = relationship('Namespace')

    def set_extra_attrs(self, obj):
        try:
            self.namespace = obj.namespace
        except AttributeError:
            log.info("Couldn't create {2} revision for {0}:{1}".format(
                self.table_name, self.record_id, self.command))
            log.info("Delta is {0}".format(self.delta))
            log.info("Thread is: {0}".format(obj.thread_id))
            raise

HasRevisions = gen_rev_role(Transaction)


class SearchToken(Base):
    """A token to prefix-match against for contacts search.
    Right now these tokens consist of:
    - the contact's full name
    - the elements of the contact's name when split by whitespace
    - the contact's email address.
    """
    token = Column(String(255))
    source = Column('source', Enum('name', 'email_address'))
    contact_id = Column(ForeignKey('contact.id', ondelete='CASCADE'))
    contact = relationship('Contact', backref='token', cascade='all',
                           single_parent=True)


class SearchSignal(Base):
    """Represents a signal used for contacts search result ranking. Examples of
    signals might include number of emails sent to or received from this
    contact, or time since last interaction with the contact."""
    name = Column(String(40))
    value = Column(Integer)
    contact_id = Column(ForeignKey('contact.id', ondelete='CASCADE'),
                        nullable=False)


class MessageContactAssociation(Base):
    """Association table between messages and contacts.

    Examples
    --------
    If m is a message, get the contacts in the to: field with
    [assoc.contact for assoc in m.contacts if assoc.field == 'to_addr']

    If c is a contact, get messages sent to contact c with
    [assoc.message for assoc in c.message_associations if assoc.field ==
    ...  'to_addr']
    """
    contact_id = Column(Integer, ForeignKey('contact.id'), primary_key=True)
    message_id = Column(Integer, ForeignKey('message.id'), primary_key=True)
    field = Column(Enum('from_addr', 'to_addr', 'cc_addr', 'bcc_addr'))
    # Note: The `cascade` properties need to be a parameter of the backref
    # here, and not of the relationship. Otherwise a sqlalchemy error is thrown
    # when you try to delete a message or a contact.
    contact = relationship('Contact',
                           backref=backref('message_associations',
                                           cascade='all, delete-orphan'))
    message = relationship('Message',
                           backref=backref('contacts',
                                           cascade='all, delete-orphan'))


class Contact(Base, HasRevisions, HasPublicID):
    """Data for a user's contact."""
    account_id = Column(ForeignKey('account.id', ondelete='CASCADE'),
                        nullable=False)
    account = relationship('Account', load_on_pending=True)

    # A server-provided unique ID.
    uid = Column(String(64), nullable=False)
    # A constant, unique identifier for the remote backend this contact came
    # from. E.g., 'google', 'EAS', 'inbox'
    provider_name = Column(String(64))

    # We essentially maintain two copies of a user's contacts.
    # The contacts with source 'remote' give the contact data as it was
    # immediately after the last sync with the remote provider.
    # The contacts with source 'local' also contain any subsequent local
    # modifications to the data.
    source = Column('source', Enum('local', 'remote'))

    email_address = Column(String(254), nullable=True, index=True)
    name = Column(Text)
    # phone_number = Column(String(64))

    raw_data = Column(Text)
    search_signals = relationship(
        'SearchSignal', cascade='all',
        collection_class=attribute_mapped_collection('name'))

    # A score to use for ranking contact search results. This should be
    # precomputed to facilitate performant search.
    score = Column(Integer)

    updated_at = Column(DateTime, default=func.now(),
                        onupdate=func.current_timestamp())
    created_at = Column(DateTime, default=func.now())

    # Flag to set if the contact is deleted in a remote backend.
    # (This is an unmapped attribute, i.e., it does not correspond to a
    # database column.)
    deleted = False

    __table_args__ = (UniqueConstraint('uid', 'source', 'account_id',
                                       'provider_name'),)

    @property
    def namespace(self):
        return self.account.namespace

    def __repr__(self):
        # XXX this won't work properly with unicode (e.g. in the name)
        return ('Contact({}, {}, {}, {}, {}, {})'
                .format(self.uid, self.name, self.email_address, self.source,
                        self.provider_name, self.deleted))

    def copy_from(self, src):
        """ Copy fields from src."""
        self.account_id = src.account_id
        self.account = src.account
        self.uid = src.uid
        self.name = src.name
        self.email_address = src.email_address
        self.provider_name = src.provider_name
        self.raw_data = src.raw_data

    @validates('name', include_backrefs=False)
    def tokenize_name(self, key, name):
        """ Update the associated search tokens whenever the contact's name is
        updated."""
        new_tokens = []
        # Delete existing 'name' tokens
        self.token = [token for token in self.token if token.source != 'name']
        if name is not None:
            new_tokens.extend(name.split())
            new_tokens.append(name)
            self.token.extend(SearchToken(token=token, source='name') for token
                              in new_tokens)
        return name

    @validates('email_address', include_backrefs=False)
    def tokenize_email_address(self, key, email_address):
        """ Update the associated search tokens whenever the contact's email
        address is updated."""
        self.token = [token for token in self.token if token.source !=
                      'email_address']
        if email_address is not None:
            new_token = SearchToken(token=email_address,
                                    source='email_address')
            self.token.append(new_token)
        return email_address


class Message(Base, HasRevisions, HasPublicID):
    # XXX clean this up a lot - make a better constructor, maybe taking
    # a flanker object as an argument to prefill a lot of attributes

    # Do delete messages if their associated thread is deleted.
    thread_id = Column(Integer, ForeignKey('thread.id', ondelete='CASCADE'),
                       nullable=False)
    thread = relationship('Thread',
                          backref=backref('messages',
                          order_by='Message.received_date'))

    from_addr = Column(JSON, nullable=True)
    sender_addr = Column(JSON, nullable=True)
    reply_to = Column(JSON, nullable=True)
    to_addr = Column(JSON, nullable=True)
    cc_addr = Column(JSON, nullable=True)
    bcc_addr = Column(JSON, nullable=True)
    in_reply_to = Column(JSON, nullable=True)
    message_id_header = Column(String(255), nullable=True)
    subject = Column(Text, nullable=True)
    received_date = Column(DateTime, nullable=False)
    size = Column(Integer, nullable=False)
    data_sha256 = Column(String(255), nullable=True)

    mailing_list_headers = Column(JSON, nullable=True)

    is_draft = Column(Boolean, server_default=false(), nullable=False)

    # Most messages are short and include a lot of quoted text. Preprocessing
    # just the relevant part out makes a big difference in how much data we
    # need to send over the wire.
    # Maximum length is determined by typical email size limits (25 MB body +
    # attachments on Gmail), assuming a maximum # of chars determined by
    # 1-byte (ASCII) chars.
    # NOTE: always HTML :)
    sanitized_body = Column(Text(length=26214400), nullable=False)
    snippet = Column(String(191), nullable=False)

    # we had to replace utf-8 errors before writing... this might be a
    # mail-parsing bug, or just a message from a bad client.
    decode_error = Column(Boolean, server_default=false(), nullable=False)

    # only on messages from Gmail
    g_msgid = Column(BigInteger, nullable=True, index=True)
    g_thrid = Column(BigInteger, nullable=True, index=True)

    # The uid as set in the X-INBOX-ID header of a sent message we create
    inbox_uid = Column(String(64), nullable=True)

    # In accordance with JWZ (http://www.jwz.org/doc/threading.html)
    references = Column(JSON, nullable=True)

    @property
    def namespace(self):
        return self.thread.namespace

    def calculate_sanitized_body(self):
        plain_part, html_part = self.body
        snippet_length = 191
        if html_part:
            assert '\r' not in html_part, "newlines not normalized"

            # Rudimentary stripping out quoted text in 'gmail_quote' div
            # Wrap this in a try/catch because sometimes BeautifulSoup goes
            # down a dark spiral of recursion death
            try:
                soup = BeautifulSoup(html_part.strip(), "lxml")
                for div in soup.findAll('div', 'gmail_quote'):
                    div.extract()
                for container in soup.findAll('div', 'gmail_extra'):
                    if container.contents is not None:
                        for tag in reversed(container.contents):
                            if not hasattr(tag, 'name') or tag.name != 'br':
                                break
                            else:
                                tag.extract()
                    if container.contents is None:
                        # we emptied it!
                        container.extract()

                # Paragraphs don't need trailing line-breaks.
                for container in soup.findAll('p'):
                    if container.contents is not None:
                        for tag in reversed(container.contents):
                            if not hasattr(tag, 'name') or tag.name != 'br':
                                break
                            else:
                                tag.extract()

                # Misc other crap.
                dtd = [item for item in soup.contents if isinstance(
                    item, Doctype)]
                comments = soup.findAll(text=lambda text: isinstance(
                    text, Comment))
                for tag in chain(dtd, comments):
                    tag.extract()
                self.sanitized_body = unicode(soup)

                # trim for snippet
                for tag in soup.findAll(['style', 'head', 'title']):
                    tag.extract()
                self.snippet = soup.get_text(' ')[:191]

            except RuntimeError as exc:
                err_prefix = 'maximum recursion depth exceeded'
                # e.message is deprecated in Python 3
                if exc.args[0].startswith(err_prefix):
                    full_traceback = 'Ignoring error: {}\nOuter stack:\n{}{}'\
                        .format(exc, ''.join(traceback.format_stack()[:-2]),
                                traceback.format_exc(exc))

                    # Note that python doesn't support tail call recursion
                    # optimizations
                    # http://neopythonic.blogspot.com/2009/04/tail-recursion-elimination.html
                    full_traceback = 'Error in BeautifulSoup.' + \
                        'System recursion limit: {0}'.format(
                            sys.getrecursionlimit()) + \
                        '\n\n\n' + \
                        full_traceback

                    # TODO have a better logging service for storing these
                    errdir = os.path.join(config['LOGDIR'],
                                          'bs_parsing_errors', )
                    errfile = os.path.join(errdir, str(self.data_sha256))
                    mkdirp(errdir)

                    with open("{0}_traceback".format(errfile), 'w') as fh:
                        fh.write(full_traceback)
                    # Write the file in binary mode, since it might also have
                    # decoding errors.
                    with open("{0}_data".format(errfile), 'wb') as fh:
                        fh.write(html_part.encode("utf-8"))

                    log.error("BeautifulSoup parsing error. Data logged to\
                              {0}_data and {0}_traceback".format(errfile))
                    self.decode_error = True

                    # Not sanitized, but will still work
                    self.sanitized_body = html_part
                    self.snippet = soup.get_text(' ')[:191]

                else:
                    log.error("Unknown BeautifulSoup exception: {0}".format(
                        exc))
                    raise exc

        elif plain_part is None:
            self.sanitized_body = u''
            self.snippet = u''
        else:
            stripped = strip_plaintext_quote(plain_part.strip())
            self.sanitized_body = plaintext2html(stripped)
            self.snippet = stripped[:snippet_length]

    @property
    def body(self):
        """ Returns (plaintext, html) body for the message, decoded. """
        assert self.parts, \
            "Can't calculate body before parts have been parsed"

        plain_data = None
        html_data = None

        for part in self.parts:
            if part.content_type == 'text/html':
                html_data = part.data.decode('utf-8')
                break
        for part in self.parts:
            if part.content_type == 'text/plain':
                plain_data = part.data.decode('utf-8')
                break

        return plain_data, html_data

    def trimmed_subject(self):
        s = self.subject
        if s[:4] == u'RE: ' or s[:4] == u'Re: ':
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
                                '..', 'message_template.html')
            with open(path, 'r') as f:
                # template has %s in it. can't do format because python
                # misinterprets css
                prettified = f.read() % html_data

        return prettified

    @property
    def mailing_list_info(self):
        return self.mailing_list_headers

    @property
    def headers(self):
        """ Returns headers for the message, decoded. """
        assert self.parts, \
            "Can't provide headers before parts have been parsed"

        headers = self.parts[0].data
        json_headers = json.JSONDecoder().decode(headers)

        return json_headers

    @property
    def folders(self):
        return [folder.folder_name for folder in self.thread.folders]

    # The return value of this method will be stored in the transaction log's
    # `additional_data` column.
    def get_versioned_properties(self):
        from inbox.server.models.kellogs import APIEncoder
        encoder = APIEncoder()
        return {'thread': encoder.default(self.thread),
                'namespace_public_id': self.namespace.public_id,
                'blocks': [encoder.default(part) for part in self.parts]}

    discriminator = Column('type', String(16))
    __mapper_args__ = {'polymorphic_on': discriminator,
                       'polymorphic_identity': 'message'}


class SpoolMessage(Message):
    """
    Messages sent from this client.

    Stored so they are immediately available to the user. They are reconciled
    with the messages we get from the remote backend in a subsequent sync.
    """
    id = Column(Integer, ForeignKey('message.id', ondelete='CASCADE'),
                primary_key=True)

    created_date = Column(DateTime)
    is_sent = Column(Boolean, server_default=false(), nullable=False)

    # Null till reconciled.
    resolved_message_id = Column(Integer,
                                 ForeignKey('message.id', ondelete='CASCADE'),
                                 nullable=True)
    resolved_message = relationship(
        'Message',
        primaryjoin='SpoolMessage.resolved_message_id==Message.id',
        backref=backref('spooled_message', uselist=False))

    __mapper_args__ = {'polymorphic_identity': 'spoolmessage',
                       'inherit_condition': id == Message.id}


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


class Block(Blob, Base, HasRevisions, HasPublicID):
    """ Metadata for any file that we store """

    # Save some space with common content types
    _content_type_common = Column(Enum(*common_content_types))
    _content_type_other = Column(String(255))
    filename = Column(String(255))

    # TODO: create a constructor that allows the 'content_type' keyword
    def __init__(self, *args, **kwargs):
        self.content_type = None
        self.size = 0
        Base.__init__(self, *args, **kwargs)

    def __repr__(self):
        return 'Block: %s' % self.__dict__

    namespace_id = Column(Integer,
                          ForeignKey('namespace.id', ondelete='CASCADE'),
                          nullable=False)
    namespace = relationship('Namespace', backref=backref('blocks'))

    @reconstructor
    def init_on_load(self):
        if self._content_type_common:
            self.content_type = self._content_type_common
        else:
            self.content_type = self._content_type_other


@event.listens_for(Block, 'before_insert', propagate=True)
def serialize_before_insert(mapper, connection, target):
    if target.content_type in common_content_types:
        target._content_type_common = target.content_type
        target._content_type_other = None
    else:
        target._content_type_common = None
        target._content_type_other = target.content_type


class Part(Block):
    """ Part is a section of a specific message. This includes message bodies
        as well as attachments.
    """

    id = Column(Integer, ForeignKey('block.id', ondelete='CASCADE'),
                primary_key=True)

    message_id = Column(Integer, ForeignKey('message.id', ondelete='CASCADE'))
    message = relationship('Message',
                           backref=backref(
                               "parts", cascade="all, delete, delete-orphan"))

    walk_index = Column(Integer)
    content_disposition = Column(Enum('inline', 'attachment'))
    content_id = Column(String(255))  # For attachments
    misc_keyval = Column(JSON)

    is_inboxapp_attachment = Column(Boolean, server_default=false())

    __table_args__ = (UniqueConstraint('message_id', 'walk_index'),)

    @property
    def thread_id(self):
        if not self.message:
            return None
        return self.message.thread_id

    @property
    def is_attachment(self):
        return self.content_disposition is not None

    @property
    def namespace(self):
        if not self.message:
            return None
        return self.message.namespace


class FolderItem(Base, HasRevisions):
    """ Maps threads to folders.

    Threads in this table are the _Inbox_ datastore abstraction, which may
    be different from folder names in the actual account backends.
    """
    thread_id = Column(Integer, ForeignKey('thread.id', ondelete='CASCADE'),
                       nullable=False)
    # thread relationship is on Thread to make delete-orphan cascade work

    folder_name = Column(String(191), index=True)

    @property
    def namespace(self):
        return self.thread.namespace

    __table_args__ = (UniqueConstraint('folder_name', 'thread_id'),)


class Thread(Base, HasPublicID):
    """ Threads are a first-class object in Inbox. This thread aggregates
        the relevant thread metadata from elsewhere so that clients can only
        query on threads.

        A thread can be a member of an arbitrary number of folders.

        If you're attempting to display _all_ messages a la Gmail's All Mail,
        don't query based on folder!
    """
    subject = Column(Text, nullable=True)
    subjectdate = Column(DateTime, nullable=False)
    recentdate = Column(DateTime, nullable=False)

    folders = relationship('FolderItem', backref="thread", single_parent=True,
                           order_by="FolderItem.folder_name",
                           cascade='all, delete, delete-orphan')

    namespace_id = Column(ForeignKey('namespace.id', ondelete='CASCADE'),
                          nullable=False, index=True)
    namespace = relationship('Namespace', backref='threads')

    mailing_list_headers = Column(JSON, nullable=True)

    def update_from_message(self, message):
        if message.received_date > self.recentdate:
            self.recentdate = message.received_date
        # subject is subject of original message in the thread
        if message.received_date < self.recentdate:
            self.subject = message.subject
            self.subjectdate = message.received_date

        if len(message.mailing_list_headers) > len(self.mailing_list_headers):
            self.mailing_list_headers = message.mailing_list_headers
        return self

    @property
    def mailing_list_info(self):
        return self.mailing_list_headers

    def is_mailing_list_thread(self):
        for v in self.mailing_list_headers.itervalues():
            if (v is not None):
                return True
        return False

    @property
    def snippet(self):
        if len(self.messages):
            # Get the snippet from the most recent message
            return self.messages[-1].snippet
        return ""

    @property
    def participants(self):
        p = set()
        for m in self.messages:
            p.update(tuple(entry) for entry in
                     itertools.chain(m.from_addr, m.to_addr,
                                     m.cc_addr, m.bcc_addr))
        return p

    discriminator = Column('type', String(16))
    __mapper_args__ = {'polymorphic_on': discriminator}


class Webhook(Base, HasPublicID):
    """ hooks that run on new messages/events """

    namespace_id = Column(ForeignKey('namespace.id', ondelete='CASCADE'),
                          nullable=False, index=True)
    namespace = relationship('Namespace')

    lens_id = Column(ForeignKey('lens.id', ondelete='CASCADE'),
                     nullable=False, index=True)
    lens = relationship('Lens')

    callback_url = Column(Text, nullable=False)
    failure_notify_url = Column(Text)

    include_body = Column(Boolean, nullable=False)
    max_retries = Column(Integer, nullable=False, server_default='3')
    retry_interval = Column(Integer, nullable=False, server_default='60')
    active = Column(Boolean, nullable=False, server_default=true())

    min_processed_id = Column(Integer, nullable=False, server_default='0')


LENS_LIMIT_DEFAULT = 100


class Lens(Base, HasPublicID):
    """
    The container for a filter to match over data.

    String parameters that begin and end with '/' are interpreted as Python
    regular expressions and matched against the beginning of a string.
    Otherwise exact string matching is applied. Callers using backslashes in
    regexen must either escape them or pass the argument as a raw string (e.g.,
    r'\W+').

    Note: by default, if Lens objects instantiated within a SQLalchemy session,
    they are expunged by default. This is because we often use them to create
    temporary database or transactional filters, and don't want to save those
    filters to the database. If you *do* want to save them (ie: not expunge)
    then set detached=False in the constructor.


    Parameters
    ----------
    email: string or unicode
        Match a name or email address in any of the from, to, cc or bcc fields.
    to_addr, from_addr, cc_addr, bcc_addr: string or unicode
        Match a name or email address in the to, from, cc or bcc fields.
    folder_name: string or unicode
        Match messages contained in the given folder.
    filename: string or unicode
        Match messages that have an attachment matching the given filename.
    thread: integer
        Match messages with given public thread id.
    started_before: datetime.datetime
        Match threads whose first message is dated before the given time.
    started_after: datetime.datetime
        Match threads whose first message is dated after the given time.
    last_message_before: datetime.datetime
        Match threads whose last message is dated before the given time.
    last_message_after: datetime.datetime
        Match threads whose last message is dated after the given time.



    A Lens object can also be used for constructing database queries from
    a given set of parameters.


    Examples
    --------
    >>> from inbox.server.models import session_scope
    >>> filter = Lens(namespace_id=1, subject='Welcome to Gmail')
    >>> with session_scope() as db_session:
    ...    msg_query = filter.message_query(db_session)
    ...    print msg_query.all()
    ...    thread_query = filter.message_query(db_session)
    ...    print thread_query.all()
    [<inbox.server.models.tables.base.Message object at 0x3a31810>]
    [<inbox.server.models.tables.imap.ImapThread object at 0x3a3e550>]


    Raises
    ------
    ValueError: If an invalid regex is supplied as a parameter.


    """

    namespace_id = Column(ForeignKey('namespace.id', ondelete='CASCADE'),
                          nullable=False, index=True)
    namespace = relationship('Namespace')

    subject = Column(String(255))
    thread_public_id = Column(Base36UID)

    started_before = Column(DateTime)
    started_after = Column(DateTime)
    last_message_before = Column(DateTime)
    last_message_after = Column(DateTime)

    any_email = Column(String(255))
    to_addr = Column(String(255))
    from_addr = Column(String(255))
    cc_addr = Column(String(255))
    bcc_addr = Column(String(255))

    filename = Column(String(255))

    # TODO make tags a reference to the actual column
    tag = Column(String(255))

    # TODO add reference to tags within a filter
    # a = Column(Integer, ForeignKey('thread.id', ondelete='CASCADE'),
    #                    nullable=False)
    # thread = relationship('Thread', backref=backref('messages',
    #                       order_by='Message.received_date'))

    def __init__(self, namespace_id=None, subject=None, thread_public_id=None,
                 started_before=None, started_after=None,
                 last_message_before=None, last_message_after=None,
                 any_email=None, to_addr=None, from_addr=None, cc_addr=None,
                 bcc_addr=None, filename=None, tag=None, detached=True):

        self.namespace_id = namespace_id
        self.subject = subject
        self.thread_public_id = thread_public_id
        self.started_before = started_before
        self.started_after = started_after
        self.last_message_before = last_message_before
        self.last_message_after = last_message_after
        self.any_email = any_email
        self.to_addr = to_addr
        self.from_addr = from_addr
        self.cc_addr = cc_addr
        self.bcc_addr = bcc_addr
        self.filename = filename
        self.tag = tag

        if detached and object_session(self) is not None:
            s = object_session(self)
            s.expunge(self)
            # Note, you can later add this object to a session by doing
            # session.merge(detached_objecdt)

        # For transaction filters
        self.filters = []
        self.setup_filters()

    @reconstructor
    def setup_filters(self):

        self.filters = []

        def add_string_filter(filter_string, selector):
            if filter_string is None:
                return

            if filter_string.startswith('/') and filter_string.endswith('/'):
                try:
                    regex = re.compile(filter_string[1:-1])
                except re.error:
                    raise ValueError('Invalid regex argument')
                predicate = regex.match
            else:
                predicate = lambda candidate: filter_string == candidate

            def matcher(message):
                field = selector(message)
                if isinstance(field, basestring):
                    if not predicate(field):
                        return False
                else:
                    if not any(predicate(elem) for elem in field):
                        return False
                return True

            self.filters.append(matcher)

        #
        # Methods related to creating a transactional lens. use `match()`

        def get_subject(message):
            return message['subject']

        def get_tags(message):
            return message['thread']['tags']

        def flatten_field(field):
            """Given a list of (name, email) pairs, return an iterator over all
            the names and emails. If field is None, return the empty iterator.

            Parameters
            ----------
            field: list of iterables

            Returns
            -------
            iterable

            Example
            -------
            >>> list(flatten_field([('Name', 'email'),
            ...                     ('Another Name', 'another email')]))
            ['Name', 'email', 'Another Name', 'another email']
            """
            return itertools.chain(*field) if field is not None else ()

        def get_to(message):
            return flatten_field(message['to_addr'])

        def get_from(message):
            return flatten_field(message['from_addr'])

        def get_cc(message):
            return flatten_field(message['cc_addr'])

        def get_bcc(message):
            return flatten_field(message['bcc_addr'])

        def get_emails(message):
            return itertools.chain(func(message) for func in
                                   (get_to, get_from, get_cc, get_bcc))

        def get_filenames(message):
            return (block['filename'] for block in message['blocks']
                    if block['filename'] is not None)

        add_string_filter(self.subject, get_subject)
        add_string_filter(self.to_addr, get_to)
        add_string_filter(self.from_addr, get_from)
        add_string_filter(self.cc_addr, get_cc)
        add_string_filter(self.bcc_addr, get_bcc)
        add_string_filter(self.tag, get_tags)
        add_string_filter(self.any_email, get_emails)
        add_string_filter(self.filename, get_filenames)

        if self.thread_public_id is not None:
            self.filters.append(
                lambda message: message['thread']['id']
                == self.thread_public_id)

        if self.started_before is not None:
            self.filters.append(
                lambda message: (message['thread']['subject_date'] <
                                 self.started_before))

        if self.started_after is not None:
            self.filters.append(
                lambda message: (message['thread']['subject_date'] >
                                 self.started_after))

        if self.last_message_before is not None:
            self.filters.append(
                lambda message: (message['thread']['recent_date'] <
                                 self.last_message_before))

        if self.last_message_after is not None:
            self.filters.append(
                lambda message: (message['thread']['recent_date'] >
                                 self.last_message_after))

    def match(self, message_dict):
        """Returns True if and only if the given message matches all
        filtering criteria."""
        return all(filter(message_dict) for filter in self.filters)

    #
    # Methods related to creating a sqlalchemy filter

    def message_query(self, db_session, limit=LENS_LIMIT_DEFAULT, offset=0):
        """Return a query object which filters messages by the instance's query
        parameters."""
        self.db_session = db_session
        query = self._message_subquery()
        subquery = self._thread_subquery()
        query = maybe_refine_query(query, subquery).distinct(). \
            order_by(asc(Message.id))
        if limit > 0:
            return query.limit(limit).offset(offset)
        return query

    def thread_query(self, db_session, limit=LENS_LIMIT_DEFAULT, offset=0):
        """Return a query object which filters threads by the instance's query
        parameters."""
        self.db_session = db_session
        query = self._thread_subquery()
        subquery = self._message_subquery()
        # TODO(emfree): If there are no message-specific parameters, we may be
        # doing a join on all messages here. Not ideal.
        query = maybe_refine_query(query, subquery).distinct(). \
            order_by(asc(Thread.id))
        if limit > 0:
            return query.limit(limit).offset(offset)
        return query

    # The following private methods return individual parts of the eventual
    # composite query.

    def _message_subquery(self):
        query = self.db_session.query(Message)
        if self.subject is not None:
            # import pdb; pdb.set_trace()
            query = query.filter(Message.subject == self.subject)

        query = maybe_refine_query(query, self._from_subquery())
        query = maybe_refine_query(query, self._to_subquery())
        query = maybe_refine_query(query, self._cc_subquery())
        query = maybe_refine_query(query, self._bcc_subquery())
        query = maybe_refine_query(query, self._email_subquery())
        query = maybe_refine_query(query, self._filename_subquery())
        return query

    def _from_subquery(self):
        if self.from_addr is None:
            return None
        predicate = and_(
            or_(Contact.email_address == self.from_addr, Contact.name ==
                self.from_addr),
            MessageContactAssociation.field == 'from_addr')
        return self.db_session.query(MessageContactAssociation). \
            join(Contact).filter(predicate)

    def _to_subquery(self):
        if self.to_addr is None:
            return None
        predicate = and_(
            or_(Contact.email_address == self.to_addr,
                Contact.name == self.to_addr),
            MessageContactAssociation.field == 'to_addr')
        return self.db_session.query(MessageContactAssociation). \
            join(Contact).filter(predicate)

    def _cc_subquery(self):
        if self.cc_addr is None:
            return None
        predicate = and_(
            or_(Contact.email_address == self.cc_addr,
                Contact.name == self.cc_addr),
            MessageContactAssociation.field == 'cc_addr')
        return self.db_session.query(MessageContactAssociation). \
            join(Contact).filter(predicate)

    def _bcc_subquery(self):
        if self.bcc_addr is None:
            return None
        predicate = and_(
            or_(Contact.email_address == self.bcc_addr,
                Contact.name == self.bcc_addr),
            MessageContactAssociation.field == 'bcc_addr')
        return self.db_session.query(MessageContactAssociation). \
            join(Contact).filter(predicate)

    def _email_subquery(self):
        if self.any_email is None:
            return None
        predicate = and_(
            or_(Contact.email_address == self.any_email,
                Contact.name == self.any_email))
        return self.db_session.query(MessageContactAssociation). \
            join(Contact).filter(predicate)

    def _filename_subquery(self):
        if self.filename is None:
            return None
        return self.db_session.query(Block). \
            filter(Block.filename == self.filename)

    def _thread_subquery(self):
        pred = and_(Thread.namespace_id == self.namespace_id)
        if self.thread_public_id is not None:
            pred = and_(pred, Thread.public_id == self.thread_public_id)

        if self.started_before is not None:
            pred = and_(pred, Thread.subjectdate <
                        datetime.utcfromtimestamp(self.started_before))

        if self.started_after is not None:
            pred = and_(pred, Thread.subjectdate >
                        datetime.utcfromtimestamp(self.started_after))

        if self.last_message_before is not None:
            pred = and_(pred, Thread.recentdate <
                        datetime.utcfromtimestamp(self.last_message_before))

        if self.last_message_after is not None:
            pred = and_(pred, Thread.recentdate >
                        datetime.utcfromtimestamp(self.last_message_after))

        return self.db_session.query(Thread).filter(pred)
