import itertools
import os
import re
import json

from hashlib import sha256
from datetime import datetime
import bson

from sqlalchemy import (Column, Integer, BigInteger, String, DateTime, Boolean,
                        Enum, ForeignKey, Text, func, event, and_, or_, asc,
                        desc)
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import (reconstructor, relationship, backref, deferred,
                            validates, object_session)
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.types import BLOB
from sqlalchemy.sql.expression import true, false

from inbox.log import get_logger
log = get_logger()

from inbox.config import config
from inbox.sqlalchemy_ext.util import generate_public_id
from inbox.util.encoding import base36decode
from inbox.util.file import Lock, mkdirp
from inbox.util.html import (plaintext2html, strip_tags, extract_from_html,
                             extract_from_plain)
from inbox.util.misc import load_modules
from inbox.util.cryptography import encrypt_aes, decrypt_aes
from inbox.sqlalchemy_ext.util import (JSON, BigJSON, Base36UID,
                                       maybe_refine_query)
from inbox.sqlalchemy_ext.revision import Revision, gen_rev_role
from inbox.basicauth import AUTH_TYPES

from inbox.models.roles import Blob
from inbox.models import MailSyncBase
from inbox.models.mixins import HasPublicID

# The maximum Gmail label length is 225 (tested empirically). Exchange folder
# names can be up to upto 225 characters too (tested empirically). However,
# constraining Folder.`name` uniquely requires max length of 767 bytes under
# utf8mb4: http://mathiasbynens.be/notes/mysql-utf8mb4
# There are apparently ways to get around this by using innodb_large_prefix in your
# MySQL configuration, but I'm not sure how to do that with RDS.
MAX_INDEXABLE_LENGTH = 191
MAX_FOLDER_NAME_LENGTH = MAX_INDEXABLE_LENGTH

def register_backends():
    import inbox.models.tables

    # Find and import
    modules = load_modules(inbox.models.tables)

    # Create mapping
    table_mod_for = {}
    for module in modules:
        if hasattr(module, 'PROVIDER'):
            provider = module.PROVIDER
            table_mod_for[provider] = module

    return table_mod_for


class Account(MailSyncBase, HasPublicID):
    # http://stackoverflow.com/questions/386294/what-is-the-maximum-length-of-a-valid-email-address
    email_address = Column(String(MAX_INDEXABLE_LENGTH), nullable=True, index=True)
    provider = Column(Enum('Gmail', 'Outlook', 'Yahoo', 'EAS', 'Inbox'),
                      nullable=False)

    # We prefix user-created folder with this string when we expose them as
    # tags through the API. E.g., a 'jobs' folder/label on a Gmail backend is
    # exposed as 'gmail-jobs'.
    # Any value stored here should also be in Tag.RESERVED_PROVIDER_NAMES.
    provider_prefix = Column(String(64), nullable=False)

    # local flags & data
    save_raw_messages = Column(Boolean, server_default=true())

    sync_host = Column(String(255), nullable=True)
    last_synced_contacts = Column(DateTime, nullable=True)

    # Folder mappings for the data we sync back to the account backend.  All
    # account backends will not provide all of these. This may mean that Inbox
    # creates some folders on the remote backend, for example to provide
    # "archive" functionality on non-Gmail remotes.
    inbox_folder_id = Column(Integer,
                             ForeignKey('folder.id', ondelete='SET NULL'),
                             nullable=True)
    inbox_folder = relationship(
        'Folder', post_update=True,
        primaryjoin='and_(Account.inbox_folder_id == Folder.id, '
                    'Folder.deleted_at.is_(None))')
    sent_folder_id = Column(Integer,
                            ForeignKey('folder.id', ondelete='SET NULL'),
                            nullable=True)
    sent_folder = relationship(
        'Folder', post_update=True,
        primaryjoin='and_(Account.sent_folder_id == Folder.id, '
                    'Folder.deleted_at.is_(None))')

    drafts_folder_id = Column(Integer,
                              ForeignKey('folder.id', ondelete='SET NULL'),
                              nullable=True)
    drafts_folder = relationship(
        'Folder', post_update=True,
        primaryjoin='and_(Account.drafts_folder_id == Folder.id, '
                    'Folder.deleted_at.is_(None))')

    spam_folder_id = Column(Integer,
                            ForeignKey('folder.id', ondelete='SET NULL'),
                            nullable=True)
    spam_folder = relationship(
        'Folder', post_update=True,
        primaryjoin='and_(Account.spam_folder_id == Folder.id, '
                    'Folder.deleted_at.is_(None))')

    trash_folder_id = Column(Integer,
                             ForeignKey('folder.id', ondelete='SET NULL'),
                             nullable=True)
    trash_folder = relationship(
        'Folder', post_update=True,
        primaryjoin='and_(Account.trash_folder_id == Folder.id, '
                    'Folder.deleted_at.is_(None))')

    archive_folder_id = Column(Integer,
                               ForeignKey('folder.id', ondelete='SET NULL'),
                               nullable=True)
    archive_folder = relationship(
        'Folder', post_update=True,
        primaryjoin='and_(Account.archive_folder_id == Folder.id, '
                    'Folder.deleted_at.is_(None))')

    all_folder_id = Column(Integer,
                           ForeignKey('folder.id', ondelete='SET NULL'),
                           nullable=True)
    all_folder = relationship(
        'Folder', post_update=True,
        primaryjoin='and_(Account.all_folder_id == Folder.id, '
                    'Folder.deleted_at.is_(None))')

    starred_folder_id = Column(Integer,
                               ForeignKey('folder.id', ondelete='SET NULL'),
                               nullable=True)
    starred_folder = relationship(
        'Folder', post_update=True,
        primaryjoin='and_(Account.starred_folder_id == Folder.id, '
                    'Folder.deleted_at.is_(None))')

    important_folder_id = Column(Integer,
                                 ForeignKey('folder.id', ondelete='SET NULL'),
                                 nullable=True)
    important_folder = relationship(
        'Folder', post_update=True,
        primaryjoin='and_(Account.important_folder_id == Folder.id, '
                    'Folder.deleted_at.is_(None))')

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


class Namespace(MailSyncBase, HasPublicID):
    """ A way to do grouping / permissions, basically. """
    # NOTE: only root namespaces have account backends
    account_id = Column(Integer,
                        ForeignKey('account.id', ondelete='CASCADE'),
                        nullable=True)
    # really the root_namespace
    account = relationship('Account',
                           lazy='joined',
                           backref=backref('namespace', uselist=False,
                                           primaryjoin='and_('
                                           'Account.id==Namespace.account_id, '
                                           'Namespace.deleted_at.is_(None))'),
                           uselist=False,
                           primaryjoin='and_('
                           'Namespace.account_id == Account.id, '
                           'Account.deleted_at.is_(None))')

    # invariant: imapaccount is non-null iff type is root
    type = Column(Enum('root', 'shared_folder'), nullable=False,
                  server_default='root')

    @property
    def email_address(self):
        if self.account is not None:
            return self.account.email_address


class Transaction(MailSyncBase, Revision, HasPublicID):
    """ Transactional log to enable client syncing. """
    # Do delete transactions if their associated namespace is deleted.
    namespace_id = Column(Integer,
                          ForeignKey('namespace.id', ondelete='CASCADE'),
                          nullable=False)
    namespace = relationship(
        'Namespace',
        primaryjoin='and_(Transaction.namespace_id == Namespace.id, '
                    'Namespace.deleted_at.is_(None))')

    object_public_id = Column(String(191), nullable=True)

    # The API representation of the object at the time the transaction is
    # generated.
    public_snapshot = Column(BigJSON)
    # Dictionary of any additional properties we wish to snapshot when the
    # transaction is generated.
    private_snapshot = Column(BigJSON)

    def set_extra_attrs(self, obj):
        try:
            self.namespace = obj.namespace
        except AttributeError:
            log.info("Couldn't create {2} revision for {0}:{1}".format(
                self.table_name, self.record_id, self.command))
            log.info("Delta is {0}".format(self.delta))
            log.info("Thread is: {0}".format(obj.thread_id))
            raise
        object_public_id = getattr(obj, 'public_id', None)
        if object_public_id is not None:
            self.object_public_id = object_public_id

    def take_snapshot(self, obj):
        """Record the API's representation of `obj` at the time this
        transaction is generated, as well as any other properties we want to
        have available in the transaction log. Used for client syncing and
        webhooks."""
        from inbox.models.kellogs import APIEncoder
        encoder = APIEncoder()
        self.public_snapshot = encoder.default(obj)

        if isinstance(obj, Message):
            self.private_snapshot = {
                'recentdate': obj.thread.recentdate,
                'subjectdate': obj.thread.subjectdate,
                'filenames': [part.filename for part in obj.parts if
                              part.is_attachment]}


HasRevisions = gen_rev_role(Transaction)


class SearchToken(MailSyncBase):
    """A token to prefix-match against for contacts search.
    Right now these tokens consist of:
    - the contact's full name
    - the elements of the contact's name when split by whitespace
    - the contact's email address.
    """
    token = Column(String(255))
    source = Column('source', Enum('name', 'email_address'))
    contact_id = Column(ForeignKey('contact.id', ondelete='CASCADE'))
    contact = relationship(
        'Contact', backref=backref('token',
                                   primaryjoin='and_('
                                   'Contact.id == SearchToken.contact_id, '
                                   'SearchToken.deleted_at.is_(None))'),
        cascade='all',
        primaryjoin='and_(SearchToken.contact_id == Contact.id, '
                    'Contact.deleted_at.is_(None))',
        single_parent=True)


class SearchSignal(MailSyncBase):
    """Represents a signal used for contacts search result ranking. Examples of
    signals might include number of emails sent to or received from this
    contact, or time since last interaction with the contact."""
    name = Column(String(40))
    value = Column(Integer)
    contact_id = Column(ForeignKey('contact.id', ondelete='CASCADE'),
                        nullable=False)


class MessageContactAssociation(MailSyncBase):
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
    contact = relationship(
        'Contact',
        primaryjoin='and_(MessageContactAssociation.contact_id == Contact.id, '
        'Contact.deleted_at.is_(None))',
        backref=backref('message_associations',
                        primaryjoin='and_('
                        'MessageContactAssociation.contact_id == Contact.id, '
                        'MessageContactAssociation.deleted_at.is_(None))',
                        cascade='all, delete-orphan'))
    message = relationship(
        'Message',
        primaryjoin='and_(MessageContactAssociation.message_id == Message.id, '
                    'Message.deleted_at.is_(None))',
        backref=backref('contacts',
                        primaryjoin='and_('
                        'MessageContactAssociation.message_id == Message.id, '
                        'MessageContactAssociation.deleted_at.is_(None))',
                        cascade='all, delete-orphan'))


class Contact(MailSyncBase, HasRevisions, HasPublicID):
    """Data for a user's contact."""
    account_id = Column(ForeignKey('account.id', ondelete='CASCADE'),
                        nullable=False)
    account = relationship(
        'Account', load_on_pending=True,
        primaryjoin='and_(Contact.account_id == Account.id, '
                    'Account.deleted_at.is_(None))')

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

    email_address = Column(String(MAX_INDEXABLE_LENGTH), nullable=True, index=True)
    name = Column(Text)
    # phone_number = Column(String(64))

    raw_data = Column(Text)
    search_signals = relationship(
        'SearchSignal', cascade='all',
        primaryjoin='and_(SearchSignal.contact_id == Contact.id, '
                    'SearchSignal.deleted_at.is_(None))',
        collection_class=attribute_mapped_collection('name'))

    # A score to use for ranking contact search results. This should be
    # precomputed to facilitate performant search.
    score = Column(Integer)

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


class Message(MailSyncBase, HasRevisions, HasPublicID):
    # XXX clean this up a lot - make a better constructor, maybe taking
    # a flanker object as an argument to prefill a lot of attributes

    # Do delete messages if their associated thread is deleted.
    thread_id = Column(Integer, ForeignKey('thread.id', ondelete='CASCADE'),
                       nullable=False)
    thread = relationship(
        'Thread',
        primaryjoin='and_(Message.thread_id == Thread.id, '
                    'Thread.deleted_at.is_(None))',
        backref=backref('messages',
                        primaryjoin='and_('
                        'Message.thread_id == Thread.id, '
                        'Message.deleted_at.is_(None))',
                        order_by='Message.received_date',
                        info={'versioned_properties': ['id']}))

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
    is_read = Column(Boolean, server_default=false(), nullable=False)

    # Most messages are short and include a lot of quoted text. Preprocessing
    # just the relevant part out makes a big difference in how much data we
    # need to send over the wire.
    # Maximum length is determined by typical email size limits (25 MB body +
    # attachments on Gmail), assuming a maximum # of chars determined by
    # 1-byte (ASCII) chars.
    # NOTE: always HTML :)
    sanitized_body = Column(Text(length=26214400), nullable=False)
    snippet = Column(String(191), nullable=False)
    SNIPPET_LENGTH = 191

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
        # TODO: also strip signatures.
        if html_part:
            assert '\r' not in html_part, "newlines not normalized"
            stripped = extract_from_html(html_part.encode('utf-8')).decode('utf-8').strip()
            self.sanitized_body = unicode(stripped)
            self.calculate_html_snippet(self.sanitized_body)
        elif plain_part:
            stripped = extract_from_plain(plain_part).strip()
            self.sanitized_body = plaintext2html(stripped, False)
            self.calculate_plaintext_snippet(stripped)
        else:
            self.sanitized_body = u''
            self.snippet = u''

    def calculate_html_snippet(self, text):
        text = text.replace('<br>', ' ').replace('<br/>', ' '). \
            replace('<br />', ' ')
        text = strip_tags(text)
        self.calculate_plaintext_snippet(text)

    def calculate_plaintext_snippet(self, text):
        self.snippet = ' '.join(text.split())[:self.SNIPPET_LENGTH]

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
        return self.thread.folders

    discriminator = Column('type', String(16))
    __mapper_args__ = {'polymorphic_on': discriminator,
                       'polymorphic_identity': 'message'}


class SpoolMessage(Message):
    """
    Messages created by this client.

    Stored so they are immediately available to the user. They are reconciled
    with the messages we get from the remote backend in a subsequent sync.
    """
    id = Column(Integer, ForeignKey('message.id', ondelete='CASCADE'),
                primary_key=True)

    created_date = Column(DateTime)
    is_sent = Column(Boolean, server_default=false(), nullable=False)

    state = Column(Enum('draft', 'sending', 'sending failed', 'sent'),
                   server_default='draft', nullable=False)

    # Null till reconciled.
    # Deletes should not be cascaded! i.e. delete on remote -> delete the
    # resolved_message *only*, not the original SpoolMessage we created.
    # We need this to correctly maintain draft versions (created on
    # update_draft())
    resolved_message_id = Column(Integer,
                                 ForeignKey('message.id'),
                                 nullable=True)
    resolved_message = relationship(
        'Message',
        primaryjoin='and_('
        'SpoolMessage.resolved_message_id==remote(Message.id), '
        'remote(Message.deleted_at)==None)',
        backref=backref('spooled_messages', primaryjoin='and_('
                        'remote(SpoolMessage.resolved_message_id)==Message.id,'
                        'remote(SpoolMessage.deleted_at)==None)'))

    ## FOR DRAFTS:

    # For non-conflict draft updates: versioning
    parent_draft_id = Column(Integer,
                             ForeignKey('spoolmessage.id', ondelete='CASCADE'),
                             nullable=True)
    parent_draft = relationship(
        'SpoolMessage',
        remote_side=[id],
        primaryjoin='and_('
        'SpoolMessage.parent_draft_id==remote(SpoolMessage.id), '
        'remote(SpoolMessage.deleted_at)==None)',
        backref=backref(
            'child_draft', primaryjoin='and_('
            'remote(SpoolMessage.parent_draft_id)==SpoolMessage.id,'
            'remote(SpoolMessage.deleted_at)==None)',
            uselist=False))

    # For conflict draft updates: copy of the original is created
    # We don't cascade deletes because deleting a draft should not delete
    # the other drafts that are updates to the same original.
    draft_copied_from = Column(Integer,
                               ForeignKey('spoolmessage.id'),
                               nullable=True)

    # For draft replies: the 'copy' of the thread it is a reply to.
    replyto_thread_id = Column(Integer, ForeignKey('draftthread.id',
                               ondelete='CASCADE'), nullable=True)
    replyto_thread = relationship(
        'DraftThread', primaryjoin='and_('
        'SpoolMessage.replyto_thread_id==remote(DraftThread.id),'
        'remote(DraftThread.deleted_at)==None)',
        backref=backref(
            'draftmessage', primaryjoin='and_('
            'remote(SpoolMessage.replyto_thread_id)==DraftThread.id,'
            'remote(SpoolMessage.deleted_at)==None)',
            uselist=False))

    @classmethod
    def get_or_copy(cls, session, draft_public_id):
        try:
            draft = session.query(cls).filter(
                SpoolMessage.public_id == draft_public_id).one()
        except NoResultFound:
            log.info('NoResultFound for draft with public_id {0}'.
                     format(draft_public_id))
            raise
        except MultipleResultsFound:
            log.info('MultipleResultsFound for draft with public_id {0}'.
                     format(draft_public_id))
            raise

        # For non-conflict draft updates i.e. the draft that has not
        # already been updated, simply return the draft. This is set as the
        # parent of the new draft we create (updating really creates a new
        # draft because drafts are immutable)
        if not draft.child_draft:
            return draft

        # For conflict draft updates i.e. the draft has already been updated,
        # return a copy of the draft, which is set as the parent of the new
        # draft created.
        assert not draft.draft_copied_from, 'Copy of a copy!'

        # We *must not* copy the following attributes:
        # 'id', 'public_id', 'child_draft', 'draft_copied_from',
        # 'replyto_thread_id', 'replyto_thread', '_sa_instance_state',
        # 'inbox_uid'
        copy_attrs = ['decode_error', 'resolved_message_id',
                      'updated_at', 'sender_addr', 'thread_id',
                      'bcc_addr', 'cc_addr', 'references', 'discriminator',
                      'deleted_at', 'sanitized_body', 'subject', 'g_msgid',
                      'from_addr', 'g_thrid', 'snippet', 'is_sent',
                      'message_id_header', 'received_date', 'size', 'to_addr',
                      'mailing_list_headers', 'is_read', 'parent_draft_id',
                      'in_reply_to', 'is_draft', 'created_at', 'data_sha256',
                      'created_date', 'reply_to']

        draft_copy = cls()
        for attr in draft.__dict__:
            if attr in copy_attrs:
                setattr(draft_copy, attr, getattr(draft, attr))

        draft_copy.thread = draft.thread
        draft_copy.resolved_message = draft.resolved_message
        draft_copy.parts = draft.parts
        draft_copy.contacts = draft.contacts

        draft_copy.parent_draft = draft.parent_draft

        draft_copy.draft_copied_from = draft.id

        if draft.replyto_thread:
            draft_copy.replyto_thread = DraftThread.create_copy(
                draft.replyto_thread)

        return draft_copy

    __mapper_args__ = {'polymorphic_identity': 'spoolmessage',
                       'inherit_condition': id == Message.id}


class DraftThread(MailSyncBase, HasPublicID):
    """
    For a reply draft message, holds references to the message it is
    created in reply to (thread_id, message_id)

    Used instead of creating a copy of the thread and appending the draft to
    the copy.
    """
    master_public_id = Column(Base36UID, nullable=False)
    thread_id = Column(Integer, ForeignKey('thread.id'), nullable=False)
    thread = relationship(
        'Thread', primaryjoin='and_('
        'DraftThread.thread_id==remote(Thread.id),'
        'remote(Thread.deleted_at)==None)',
        backref=backref(
            'draftthreads', primaryjoin='and_('
            'remote(DraftThread.thread_id)==Thread.id,'
            'remote(DraftThread.deleted_at)==None)'))
    message_id = Column(Integer, ForeignKey('message.id'),
                        nullable=False)

    @classmethod
    def create(cls, session, original):
        assert original

        # We always create a copy so don't raise, simply log.
        try:
            draftthread = session.query(cls).filter(
                DraftThread.master_public_id == original.public_id).one()
        except NoResultFound:
            log.info('NoResultFound for draft with public_id {0}'.
                     format(original.public_id))
        except MultipleResultsFound:
            log.info('MultipleResultsFound for draft with public_id {0}'.
                     format(original.public_id))

        draftthread = cls(master_public_id=original.public_id,
                          thread=original,
                          message_id=original.messages[0].id)
        return draftthread

    @classmethod
    def create_copy(cls, draftthread):
        draftthread_copy = cls(
            master_public_id=draftthread.master_public_id,
            thread=draftthread.thread,
            message_id=draftthread.message_id
        )

        return draftthread_copy

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


class Block(Blob, MailSyncBase, HasRevisions, HasPublicID):
    """ Metadata for any file that we store """

    # Save some space with common content types
    _content_type_common = Column(Enum(*common_content_types))
    _content_type_other = Column(String(255))
    filename = Column(String(255))

    # TODO: create a constructor that allows the 'content_type' keyword
    def __init__(self, *args, **kwargs):
        self.content_type = None
        self.size = 0
        MailSyncBase.__init__(self, *args, **kwargs)

    def __repr__(self):
        return 'Block: %s' % self.__dict__

    namespace_id = Column(Integer,
                          ForeignKey('namespace.id', ondelete='CASCADE'),
                          nullable=False)
    namespace = relationship(
        'Namespace', backref=backref('blocks',
                                     primaryjoin='and_('
                                     'Block.namespace_id == Namespace.id, '
                                     'Block.deleted_at.is_(None))'),
        primaryjoin='and_(Block.namespace_id==Namespace.id, '
        'Namespace.deleted_at==None)')

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
    message = relationship(
        'Message',
        primaryjoin='and_(Part.message_id==Message.id, '
        'Message.deleted_at==None)',
        backref=backref("parts", primaryjoin='and_('
                        'Part.message_id == Message.id, '
                        'Part.deleted_at.is_(None))',
                        cascade="all, delete, delete-orphan"))

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


class Thread(MailSyncBase, HasPublicID, HasRevisions):
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

    folders = association_proxy(
        'folderitems', 'folder',
        creator=lambda folder: FolderItem(folder=folder))

    @validates('folderitems', include_removes=True)
    def also_set_tag(self, key, folderitem, is_remove):
        # Also add or remove the associated tag whenever a folder is added or
        # removed.
        with object_session(self).no_autoflush:
            folder = folderitem.folder
            tag = folder.get_associated_tag(object_session(self))
            if is_remove:
                self.remove_tag(tag)
            else:
                self.apply_tag(tag)
        return folderitem

    folderitems = relationship(
        'FolderItem', backref=backref('thread',
                                      uselist=False,
                                      primaryjoin='and_('
                                      'FolderItem.thread_id==Thread.id, '
                                      'Thread.deleted_at==None)'),
        primaryjoin='and_(FolderItem.thread_id==Thread.id, '
        'FolderItem.deleted_at==None)',
        single_parent=True, collection_class=set, cascade='all, delete-orphan')

    tags = association_proxy(
        'tagitems', 'tag',
        creator=lambda tag: TagItem(tag=tag))

    namespace_id = Column(ForeignKey('namespace.id', ondelete='CASCADE'),
                          nullable=False, index=True)
    namespace = relationship(
        'Namespace',
        primaryjoin='and_(Thread.namespace_id==Namespace.id, '
                    'Namespace.deleted_at==None)',
        backref=backref('threads',
                        primaryjoin='and_('
                        'Thread.namespace_id == Namespace.id, '
                        'Thread.deleted_at.is_(None))'))

    mailing_list_headers = Column(JSON, nullable=True)

    def update_from_message(self, message):
        if isinstance(message, SpoolMessage):
            return self

        if message.received_date > self.recentdate:
            self.recentdate = message.received_date
        # subject is subject of original message in the thread
        if message.received_date < self.recentdate:
            self.subject = message.subject
            self.subjectdate = message.received_date

        if len(message.mailing_list_headers) > len(self.mailing_list_headers):
            self.mailing_list_headers = message.mailing_list_headers

        unread_tag = self.namespace.tags['unread']
        if all(message.is_read for message in self.messages):
            self.remove_tag(unread_tag)
        else:
            self.apply_tag(unread_tag)
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

    def apply_tag(self, tag, execute_action=False):
        """Add the given Tag instance to this thread. Does nothing if the tag
        is already applied. Contains extra logic for validating input and
        triggering dependent changes. Callers should use this method instead of
        directly calling Thread.tags.add(tag).

        Parameters
        ----------
        tag: Tag instance
        execute_action: bool
            True if adding the tag should trigger a syncback action.
        """
        if tag in self.tags:
            return
        # We need to directly access the tagitem object here in order to set
        # the 'action_pending' flag.
        tagitem = TagItem(thread=self, tag=tag)
        tagitem.action_pending = execute_action
        self.tagitems.add(tagitem)

        # Add or remove dependent tags.
        # TODO(emfree) this should eventually live in its own utility function.
        inbox_tag = self.namespace.tags['inbox']
        archive_tag = self.namespace.tags['archive']
        if tag == inbox_tag:
            self.tags.discard(archive_tag)
        elif tag == archive_tag:
            self.tags.discard(inbox_tag)

    def remove_tag(self, tag, execute_action=False):
        """Remove the given Tag instance from this thread. Does nothing if the
        tag isn't present. Contains extra logic for validating input and
        triggering dependent changes. Callers should use this method instead of
        directly calling Thread.tags.discard(tag).

        Parameters
        ----------
        tag: Tag instance
        execute_action: bool
            True if removing the tag should trigger a syncback action.
        """
        if tag not in self.tags:
            return
        # We need to directly access the tagitem object here in order to set
        # the 'action_pending' flag.
        tagitem = object_session(self).query(TagItem). \
            filter(TagItem.thread_id == self.id,
                   TagItem.tag_id == tag.id).one()
        tagitem.action_pending = execute_action
        self.tags.remove(tag)

        # Add or remove dependent tags.
        inbox_tag = self.namespace.tags['inbox']
        archive_tag = self.namespace.tags['archive']
        if tag == inbox_tag:
            self.tags.add(archive_tag)
        elif tag == archive_tag:
            self.tags.add(inbox_tag)

    discriminator = Column('type', String(16))
    __mapper_args__ = {'polymorphic_on': discriminator}


class Webhook(MailSyncBase, HasPublicID):
    """ hooks that run on new messages/events """

    namespace_id = Column(ForeignKey('namespace.id', ondelete='CASCADE'),
                          nullable=False, index=True)
    namespace = relationship(
        'Namespace',
        primaryjoin='and_(Webhook.namespace_id==Namespace.id, '
        'Namespace.deleted_at==None)')

    lens_id = Column(ForeignKey('lens.id', ondelete='CASCADE'),
                     nullable=False, index=True)
    lens = relationship(
        'Lens',
        primaryjoin='and_(Webhook.lens_id==Lens.id, Lens.deleted_at==None)')

    callback_url = Column(Text, nullable=False)
    failure_notify_url = Column(Text)

    include_body = Column(Boolean, nullable=False)
    max_retries = Column(Integer, nullable=False, server_default='3')
    retry_interval = Column(Integer, nullable=False, server_default='60')
    active = Column(Boolean, nullable=False, server_default=true())

    min_processed_id = Column(Integer, nullable=False, server_default='0')


LENS_LIMIT_DEFAULT = 100


class Lens(MailSyncBase, HasPublicID):
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
    >>> from inbox.models import session_scope
    >>> filter = Lens(namespace_id=1, subject='Welcome to Gmail')
    >>> with session_scope() as db_session:
    ...    msg_query = filter.message_query(db_session)
    ...    print msg_query.all()
    ...    thread_query = filter.message_query(db_session)
    ...    print thread_query.all()
    [<inbox.models.tables.base.Message object at 0x3a31810>]
    [<inbox.models.tables.imap.ImapThread object at 0x3a3e550>]


    Raises
    ------
    ValueError: If an invalid regex is supplied as a parameter.


    """

    namespace_id = Column(ForeignKey('namespace.id', ondelete='CASCADE'),
                          nullable=False, index=True)
    namespace = relationship(
        'Namespace',
        primaryjoin='and_(Lens.namespace_id==Namespace.id, '
                    'Namespace.deleted_at==None)')

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

    # Lenses are constructed from user input, so we need to validate all
    # fields.

    @validates('subject', 'any_email', 'to_addr', 'from_addr', 'cc_addr',
               'bcc_addr', 'filename', 'tag')
    def validate_length(self, key, value):
        if value is None:
            return
        if len(value) > 255:
            raise ValueError('Value for {} is too long'.format(key))
        return value

    @validates('thread_public_id')
    def validate_thread_id(self, key, value):
        if value is None:
            return
        try:
            base36decode(value)
        except ValueError:
            raise ValueError('Invalid thread id')
        return value

    @validates('started_before', 'started_after', 'last_message_before',
               'last_message_after')
    def validate_timestamps(self, key, value):
        if value is None:
            return
        try:
            dt = datetime.utcfromtimestamp(int(value))
            # Need to set tzinfo so that we can compare to datetimes that were
            # deserialized using bson.json_util.
            return dt.replace(tzinfo=bson.tz_util.utc)
        except ValueError:
            raise ValueError('Invalid timestamp value for {}'.format(key))

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

            def matcher(message_tx):
                field = selector(message_tx)
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

        def get_subject(message_tx):
            return message_tx.public_snapshot['subject']

        def get_tags(message_tx):
            return [tag['name'] for tag in message_tx.public_snapshot['tags']]

        def flatten_field(field):
            """Given a list of dictionaries, return an iterator over all the
            dictionary values. If field is None, return the empty iterator.

            Parameters
            ----------
            field: list of iterables

            Returns
            -------
            iterable

            Example
            -------
            >>> list(flatten_field([{'name': 'Some Name',
            ...                      'email': 'some email'},
            ...                     {'name': 'Another Name',
            ...                      'email': 'another email'}]))
            ['Name', 'email', 'Another Name', 'another email']
            """
            if field is not None:
                return itertools.chain.from_iterable(d.itervalues() for d in
                                                     field)
            return ()

        def get_to(message_tx):
            return flatten_field(message_tx.public_snapshot['to'])

        def get_from(message_tx):
            return flatten_field(message_tx.public_snapshot['from'])

        def get_cc(message_tx):
            return flatten_field(message_tx.public_snapshot['cc'])

        def get_bcc(message_tx):
            return flatten_field(message_tx.public_snapshot['bcc'])

        def get_emails(message_tx):
            return itertools.chain.from_iterable(
                func(message_tx) for func in (get_to, get_from, get_cc, get_bcc))

        def get_filenames(message_tx):
            return message_tx.private_snapshot['filenames']

        def get_subject_date(message_tx):
            return message_tx.private_snapshot['subjectdate']

        def get_recent_date(message_tx):
            return message_tx.private_snapshot['recentdate']

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
                lambda message_tx: message_tx.public_snapshot['thread']
                == self.thread_public_id)

        if self.started_before is not None:
            # STOPSHIP(emfree)
            self.filters.append(
                lambda message_tx: (get_subject_date(message_tx) <
                                    self.started_before))

        if self.started_after is not None:
            self.filters.append(
                lambda message_tx: (get_subject_date(message_tx) >
                                    self.started_after))

        if self.last_message_before is not None:
            self.filters.append(
                lambda message_tx: (get_recent_date(message_tx) <
                                    self.last_message_before))

        if self.last_message_after is not None:
            self.filters.append(
                lambda message_tx: (get_recent_date(message_tx) >
                                    self.last_message_after))

    def match(self, message_tx):
        """Returns True if and only if the given message matches all
        filtering criteria."""
        return all(filter(message_tx) for filter in self.filters)

    #
    # Methods related to creating a sqlalchemy filter

    def message_query(self, db_session, limit=None, offset=None, order=None):
        """Return a query object which filters messages by the instance's query
        parameters."""
        limit = limit or LENS_LIMIT_DEFAULT
        offset = offset or 0
        self.db_session = db_session
        query = self._message_subquery()
        query = maybe_refine_query(query, self._thread_subquery())
        query = query.distinct()
        if order == 'subject':
            query = query.order_by(asc(Message.subject))
        elif order == 'date':
            query = query.order_by(desc(Message.received_date))
        else:
            query = query.order_by(asc(Message.id))

        if limit > 0:
            query = query.limit(limit)
        if offset > 0:
            query = query.offset(offset)
        return query

    def thread_query(self, db_session, limit=None, offset=None, order=None):
        """Return a query object which filters threads by the instance's query
        parameters."""
        limit = limit or LENS_LIMIT_DEFAULT
        offset = offset or 0
        self.db_session = db_session
        query = self._thread_subquery()
        # TODO(emfree): If there are no message-specific parameters, we may be
        # doing a join on all messages here. Not good.
        query = maybe_refine_query(query, self._message_subquery())
        query = query.distinct()
        if order == 'subject':
            query = query.order_by(asc(Thread.subject))
        elif order == 'date':
            query = query.order_by(desc(Thread.recentdate))
        else:
            query = query.order_by(asc(Thread.id))

        if limit > 0:
            query = query.limit(limit)
        if offset > 0:
            query = query.offset(offset)
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

    def _tag_subquery(self):
        if self.tag is None:
            return None
        return self.db_session.query(TagItem).join(Tag). \
            filter(or_(Tag.name == self.tag,
                       Tag.public_id == self.tag))

    def _thread_subquery(self):
        pred = and_(Thread.namespace_id == self.namespace_id)
        if self.thread_public_id is not None:
            # TODO(emfree): currently this may return a 500 if
            # thread_public_id isn't b36-decodable.
            pred = and_(pred, Thread.public_id == self.thread_public_id)

        if self.started_before is not None:
            pred = and_(pred, Thread.subjectdate < self.started_before)

        if self.started_after is not None:
            pred = and_(pred, Thread.subjectdate > self.started_after)

        if self.last_message_before is not None:
            pred = and_(pred, Thread.recentdate < self.last_message_before)

        if self.last_message_after is not None:
            pred = and_(pred, Thread.recentdate > self.last_message_after)

        query = self.db_session.query(Thread).filter(pred)
        query = maybe_refine_query(query, self._tag_subquery())

        return query


class Folder(MailSyncBase):
    """ Folders from the remote account backend (IMAP/Exchange). """
    # `use_alter` required here to avoid circular dependency w/Account
    account_id = Column(Integer,
                        ForeignKey('account.id', use_alter=True,
                                   name='folder_fk1',
                                   ondelete='CASCADE'), nullable=False)
    account = relationship(
        'Account', backref=backref('folders',
                                   primaryjoin='and_('
                                   'Folder.account_id == Account.id, '
                                   'Folder.deleted_at.is_(None))'),
        primaryjoin='and_(Folder.account_id==Account.id, '
        'Account.deleted_at==None)')

    # Explicitly set collation to be case insensitive. This is mysql's default
    # but never trust defaults! This allows us to store the original casing to
    # not confuse users when displaying it, but still only allow a single
    # folder with any specific name, canonicalized to lowercase.
    name = Column(String(MAX_FOLDER_NAME_LENGTH,
                         collation='utf8mb4_general_ci'))

    canonical_name = Column(String(MAX_FOLDER_NAME_LENGTH))

    @property
    def namespace(self):
        return self.account.namespace

    @classmethod
    def create(cls, account, name, session, canonical_name=None):
        if len(name) > MAX_FOLDER_NAME_LENGTH:
            log.warning("Truncating long folder name for account {}; "
                        "original name was '{}'" .format(account.id, name))
            name = name[:MAX_FOLDER_NAME_LENGTH]
        obj = cls(account=account, name=name,
                  canonical_name=canonical_name)
        return obj

    @classmethod
    def find_or_create(cls, session, account, name, canonical_name=None):
        try:
            if len(name) > MAX_FOLDER_NAME_LENGTH:
                name = name[:MAX_FOLDER_NAME_LENGTH]
            obj = session.query(cls).filter(
                Folder.account_id == account.id,
                func.lower(Folder.name) == func.lower(name)).one()
        except NoResultFound:
            obj = cls.create(account, name, session, canonical_name)
        except MultipleResultsFound:
            log.info("Duplicate folder rows for folder {} for account {}"
                     .format(name, account.id))
            raise
        return obj

    def get_associated_tag(self, db_session):
        if self.canonical_name is not None:
            try:
                return db_session.query(Tag). \
                    filter(Tag.namespace_id == self.namespace.id,
                           Tag.public_id == self.canonical_name).one()
            except NoResultFound:
                # Explicitly set the namespace_id instead of the namespace
                # attribute to avoid autoflush-induced IntegrityErrors where
                # the namespace_id is null on flush.
                tag = Tag(namespace_id=self.account.namespace.id,
                          name=self.canonical_name,
                          public_id=self.canonical_name,
                          user_mutable=True)
                db_session.add(tag)
                return tag

        else:
            provider_prefix = self.account.provider_prefix
            tag_name = '-'.join((provider_prefix, self.name.lower()))
            try:
                return db_session.query(Tag). \
                    filter(Tag.namespace_id == self.namespace.id,
                           Tag.name == tag_name).one()
            except NoResultFound:
                # Explicitly set the namespace_id instead of the namespace
                # attribute to avoid autoflush-induced IntegrityErrors where
                # the namespace_id is null on flush.
                tag = Tag(namespace_id=self.account.namespace.id,
                          name=tag_name,
                          user_mutable=False)
                db_session.add(tag)
                return tag

    __table_args__ = (UniqueConstraint('account_id', 'name'),)


class FolderItem(MailSyncBase):
    """ Mapping of threads to account backend folders.

    Used to provide a read-only copy of these backend folders/labels and,
    (potentially), to sync local datastore changes to these folders back to
    the IMAP/Exchange server.

    Note that a thread may appear in more than one folder, as may be the case
    with Gmail labels.
    """
    thread_id = Column(Integer, ForeignKey('thread.id', ondelete='CASCADE'),
                       nullable=False)
    # thread relationship is on Thread to make delete-orphan cascade work

    # Might be different from what we've synced from IMAP. (Local datastore
    # changes.)
    folder_id = Column(Integer, ForeignKey('folder.id', ondelete='CASCADE'),
                       nullable=False)

    # We almost always need the folder name too, so eager load by default.
    folder = relationship(
        'Folder', uselist=False,
        backref=backref('threads',
                        # If associated folder is deleted, don't load child
                        # objects and let database-level cascade do its thing.
                        passive_deletes=True,
                        primaryjoin='and_(FolderItem.folder_id==Folder.id, '
                        'FolderItem.deleted_at==None)'),
        lazy='joined',
        primaryjoin='and_(FolderItem.folder_id==Folder.id, '
        'Folder.deleted_at==None)')

    @property
    def account(self):
        return self.folder.account

    @property
    def namespace(self):
        return self.thread.namespace


class Tag(MailSyncBase, HasRevisions):
    """Tags represent extra data associated with threads.

    A note about the schema. The 'public_id' of a tag is immutable. For
    reserved tags such as the inbox or starred tag, the public_id is a fixed
    human-readable string. For other tags, the public_id is an autogenerated
    uid similar to a normal public id, but stored as a string for
    compatibility.

    The name of a tag is allowed to be mutable, to allow for the eventuality
    that users wish to change the name of user-created labels, or that we
    someday expose localized names ('DAS INBOX'), or that we somehow manage to
    sync renamed gmail labels, etc.
    """

    namespace = relationship(
        'Namespace', backref=backref(
            'tags',
            primaryjoin='and_(Tag.namespace_id == Namespace.id, '
                        'Tag.deleted_at.is_(None))',
            collection_class=attribute_mapped_collection('public_id')),
        primaryjoin='and_(Tag.namespace_id==Namespace.id, '
        'Namespace.deleted_at.is_(None))',
        load_on_pending=True)
    # (Because this class inherits from HasRevisions, we need
    # load_on_pending=True here so that setting Transaction.namespace in
    # Transaction.set_extra_attrs() doesn't raise an IntegrityError.)
    namespace_id = Column(Integer, ForeignKey(
        'namespace.id', ondelete='CASCADE'), nullable=False)

    public_id = Column(String(191), nullable=False, default=generate_public_id)
    name = Column(String(191), nullable=False)

    user_created = Column(Boolean, server_default=false(), nullable=False)
    user_mutable = Column(Boolean, server_default=true(), nullable=False)

    RESERVED_PROVIDER_NAMES = ['gmail', 'outlook', 'yahoo', 'exchange',
                               'inbox', 'icloud', 'aol']

    RESERVED_TAG_NAMES = ['inbox', 'all', 'archive', 'drafts', 'send',
                          'sending', 'sent', 'spam', 'starred', 'unstarred',
                          'unread', 'replied', 'trash', 'file', 'attachment']

    @classmethod
    def create_canonical_tags(cls, namespace, db_session):
        """If they don't already exist yet, create tags that should always
        exist."""
        existing_canonical_tags = db_session.query(Tag).filter(
            Tag.namespace_id == namespace.id,
            Tag.public_id.in_(cls.RESERVED_TAG_NAMES)).all()
        missing_canonical_names = set(cls.RESERVED_TAG_NAMES).difference(
            {tag.public_id for tag in existing_canonical_tags})
        for canonical_name in missing_canonical_names:
            tag = Tag(namespace=namespace,
                      public_id=canonical_name,
                      name=canonical_name,
                      user_mutable=True)
            db_session.add(tag)

    @classmethod
    def name_available(cls, name, namespace_id, db_session):
        if any(name.lower().startswith(provider) for provider in
               cls.RESERVED_PROVIDER_NAMES):
            return False

        if name in cls.RESERVED_TAG_NAMES:
            return False

        if (name,) in db_session.query(Tag.name). \
                filter(Tag.namespace_id == namespace_id).all():
            return False

        return True

    __table_args__ = (UniqueConstraint('namespace_id', 'name'),
                      UniqueConstraint('namespace_id', 'public_id'))


class TagItem(MailSyncBase):
    """Mapping between user tags and threads."""
    thread_id = Column(Integer, ForeignKey('thread.id'), nullable=False)
    tag_id = Column(Integer, ForeignKey('tag.id'), nullable=False)
    thread = relationship(
        'Thread',
        backref=backref('tagitems',
                        collection_class=set,
                        cascade='all, delete-orphan',
                        primaryjoin='and_(TagItem.thread_id==Thread.id, '
                                    'TagItem.deleted_at.is_(None))',
                        info={'versioned_properties': ['tag_id',
                                                       'action_pending']}),
        primaryjoin='and_(TagItem.thread_id==Thread.id, '
        'Thread.deleted_at.is_(None))')
    tag = relationship(
        'Tag',
        backref=backref('tagitems',
                        primaryjoin='and_('
                        'TagItem.tag_id  == Tag.id, '
                        'TagItem.deleted_at.is_(None))',
                        cascade='all, delete-orphan'),
        primaryjoin='and_(TagItem.tag_id==Tag.id, '
        'Tag.deleted_at.is_(None))')

    # This flag should be set by calling code that adds or removes a tag from a
    # thread, and wants a syncback action to be associated with it as a result.
    @property
    def action_pending(self):
        if not hasattr(self, '_action_pending'):
            self._action_pending = False
        return self._action_pending

    @action_pending.setter
    def action_pending(self, value):
        self._action_pending = value

    @property
    def namespace(self):
        return self.thread.namespace
