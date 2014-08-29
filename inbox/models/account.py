from datetime import datetime

from sqlalchemy import (Column, Integer, String, DateTime, Boolean, ForeignKey,
                        Enum)
from sqlalchemy.orm import relationship
from sqlalchemy.sql.expression import true
from inbox.sqlalchemy_ext.util import generate_public_id

from inbox.sqlalchemy_ext.util import JSON, MutableDict
from inbox.util.file import Lock

from inbox.models.mixins import HasPublicID, HasEmailAddress
from inbox.models.base import MailSyncBase
from inbox.models.folder import Folder
from inbox.models.calendar import Calendar


class Account(MailSyncBase, HasPublicID, HasEmailAddress):
    @property
    def provider(self):
        """ A constant, unique lowercase identifier for the account provider
        (e.g., 'gmail', 'eas'). Subclasses should override this.

        We prefix provider folders with this string when we expose them as
        tags through the API. E.g., a 'jobs' folder/label on a Gmail
        backend is exposed as 'gmail-jobs'. Any value returned here
        should also be in Tag.RESERVED_PROVIDER_NAMES.

        """
        raise NotImplementedError

    def verify(self):
        """ Verify that the account is still valid."""
        raise NotImplementedError

    # local flags & data
    save_raw_messages = Column(Boolean, server_default=true())

    last_synced_contacts = Column(DateTime, nullable=True)
    last_synced_events = Column(DateTime, nullable=True)

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

    default_calendar_id = Column(Integer,
                                 ForeignKey('calendar.id',
                                            ondelete='SET NULL',
                                            use_alter=True,
                                            name='account_ibfk_10'),
                                 nullable=True)

    _default_calendar = relationship(
        'Calendar', post_update=True,
        primaryjoin='and_(Account.default_calendar_id == Calendar.id, '
                    'Calendar.deleted_at.is_(None))')

    @property
    def default_calendar(self):
        if not self._default_calendar:
            public_id = generate_public_id()
            new_cal = Calendar()
            new_cal.public_id = public_id
            new_cal.account = self
            new_cal.uid = public_id
            new_cal.read_only = False
            self._default_calendar = new_cal
        return self._default_calendar

    @default_calendar.setter
    def default_calendar(self, cal):
        self._default_calendar = cal

    sync_host = Column(String(255), nullable=True)

    # current state of this account
    state = Column(Enum('live', 'down', 'invalid'), nullable=True)

    @property
    def sync_enabled(self):
        return self.sync_host is not None

    sync_state = Column(Enum('running', 'stopped', 'killed',
                             'invalid', 'connerror'),
                        nullable=True)

    _sync_status = Column(MutableDict.as_mutable(JSON), default={},
                          nullable=True)

    @property
    def sync_status(self):
        d = dict(id=self.id,
                 email=self.email_address,
                 provider=self.provider,
                 is_enabled=self.sync_enabled,
                 state=self.sync_state,
                 sync_host=self.sync_host)
        d.update(self._sync_status or {})

        return d

    def start_sync(self, sync_host=None):
        # If a host isn't provided then start it as a new sync
        if sync_host:
            self.sync_started(sync_host)
        else:
            self.sync_state = None

    def sync_started(self, sync_host):
        self.sync_host = sync_host

        # Never run before
        if self.sync_state is None and \
                self._sync_status.get('sync_end_time') is None:
            self._sync_status['sync_type'] = 'new'
            self._sync_status['sync_start_time'] = datetime.utcnow()
        # Restarting stopped/killed
        else:
            self._sync_status['sync_type'] = 'resumed'
            self._sync_status['sync_restart_time'] = datetime.utcnow()

        self.sync_state = 'running'

        self._sync_status['sync_end_time'] = None
        self._sync_status['sync_error'] = None

    def stop_sync(self):
        """ Set a flag for the monitor to stop the sync. """

        # Don't overwrite state if Invalid credentials/Connection error/
        # Killed because foldersyncs were killed.
        if not self.sync_state or self.sync_state == 'running':
            self.sync_state = 'stopped'

    def sync_stopped(self):
        """ Called when the sync has actually been stopped. """
        self.sync_host = None
        self._sync_status['sync_end_time'] = datetime.utcnow()

    def kill_sync(self, error=None):
        # Don't change sync_host if moving to state 'killed'

        self.sync_state = 'killed'

        self._sync_status['sync_end_time'] = datetime.utcnow()
        self._sync_status['sync_error'] = error

    @property
    def sender_name(self):
        # Used for setting sender information when we send a message.
        # Can be overridden by subclasses that store account name information.
        return ''

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
    def is_killed(self):
        return self.sync_state == 'killed'

    @property
    def is_sync_locked(self):
        return self._sync_lock.locked()

    discriminator = Column('type', String(16))
    __mapper_args__ = {'polymorphic_identity': 'account',
                       'polymorphic_on': discriminator}
