import os
from hashlib import sha256
from sqlalchemy import (Column, Integer, String, DateTime, Boolean, Enum,
                        ForeignKey)
from sqlalchemy.orm import relationship, deferred
from sqlalchemy.types import BLOB
from sqlalchemy.sql.expression import true

from inbox.config import config
from inbox.util.file import Lock, mkdirp
from inbox.util.cryptography import encrypt_aes, decrypt_aes
from inbox.basicauth import AUTH_TYPES

from inbox.models.mixins import HasPublicID
from inbox.models.base import MailSyncBase
from inbox.models.folder import Folder

from inbox.models.base import MAX_INDEXABLE_LENGTH


class Account(MailSyncBase, HasPublicID):
    # http://stackoverflow.com/questions/386294
    email_address = Column(String(MAX_INDEXABLE_LENGTH),
                           nullable=True, index=True)
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
                             ForeignKey(Folder.id, ondelete='SET NULL'),
                             nullable=True)
    inbox_folder = relationship(
        'Folder', post_update=True,
        primaryjoin='and_(Account.inbox_folder_id == Folder.id, '
                    'Folder.deleted_at.is_(None))')
    sent_folder_id = Column(Integer,
                            ForeignKey(Folder.id, ondelete='SET NULL'),
                            nullable=True)
    sent_folder = relationship(
        'Folder', post_update=True,
        primaryjoin='and_(Account.sent_folder_id == Folder.id, '
                    'Folder.deleted_at.is_(None))')

    drafts_folder_id = Column(Integer,
                              ForeignKey(Folder.id, ondelete='SET NULL'),
                              nullable=True)
    drafts_folder = relationship(
        'Folder', post_update=True,
        primaryjoin='and_(Account.drafts_folder_id == Folder.id, '
                    'Folder.deleted_at.is_(None))')

    spam_folder_id = Column(Integer,
                            ForeignKey(Folder.id, ondelete='SET NULL'),
                            nullable=True)
    spam_folder = relationship(
        'Folder', post_update=True,
        primaryjoin='and_(Account.spam_folder_id == Folder.id, '
                    'Folder.deleted_at.is_(None))')

    trash_folder_id = Column(Integer,
                             ForeignKey(Folder.id, ondelete='SET NULL'),
                             nullable=True)
    trash_folder = relationship(
        'Folder', post_update=True,
        primaryjoin='and_(Account.trash_folder_id == Folder.id, '
                    'Folder.deleted_at.is_(None))')

    archive_folder_id = Column(Integer,
                               ForeignKey(Folder.id, ondelete='SET NULL'),
                               nullable=True)
    archive_folder = relationship(
        'Folder', post_update=True,
        primaryjoin='and_(Account.archive_folder_id == Folder.id, '
                    'Folder.deleted_at.is_(None))')

    all_folder_id = Column(Integer,
                           ForeignKey(Folder.id, ondelete='SET NULL'),
                           nullable=True)
    all_folder = relationship(
        'Folder', post_update=True,
        primaryjoin='and_(Account.all_folder_id == Folder.id, '
                    'Folder.deleted_at.is_(None))')

    starred_folder_id = Column(Integer,
                               ForeignKey(Folder.id, ondelete='SET NULL'),
                               nullable=True)
    starred_folder = relationship(
        'Folder', post_update=True,
        primaryjoin='and_(Account.starred_folder_id == Folder.id, '
                    'Folder.deleted_at.is_(None))')

    important_folder_id = Column(Integer,
                                 ForeignKey(Folder.id, ondelete='SET NULL'),
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
