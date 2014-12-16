from datetime import datetime

from sqlalchemy import (Column, Integer, String, DateTime, Boolean, ForeignKey,
                        Enum)
from sqlalchemy.orm import relationship
from sqlalchemy.sql.expression import true, false
from inbox.sqlalchemy_ext.util import generate_public_id

from inbox.sqlalchemy_ext.util import JSON, MutableDict
from inbox.util.file import Lock

from inbox.models.mixins import HasPublicID, HasEmailAddress
from inbox.models.base import MailSyncBase
from inbox.models.folder import Folder
from inbox.models.calendar import Calendar
from inbox.providers import provider_info


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

    @property
    def auth_handler(self):
        from inbox.auth import handler_from_provider
        return handler_from_provider(self.provider)

    @property
    def provider_info(self):
        return provider_info(self.provider, self.email_address)

    def verify(self):
        """ Verify that the account is still valid."""
        raise NotImplementedError

    @property
    def thread_cls(self):
        from inbox.models.thread import Thread
        return Thread

    # The default phrase used when sending mail from this account.
    name = Column(String(256), nullable=False, server_default='')

    # If True, throttle initial sync to reduce resource load
    throttled = Column(Boolean, server_default=false())

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
    inbox_folder = relationship('Folder', post_update=True,
                                foreign_keys=[inbox_folder_id])
    sent_folder_id = Column(Integer,
                            ForeignKey(Folder.id, ondelete='SET NULL'),
                            nullable=True)
    sent_folder = relationship('Folder', post_update=True,
                               foreign_keys=[sent_folder_id])

    drafts_folder_id = Column(Integer,
                              ForeignKey(Folder.id, ondelete='SET NULL'),
                              nullable=True)
    drafts_folder = relationship('Folder', post_update=True,
                                 foreign_keys=[drafts_folder_id])

    spam_folder_id = Column(Integer,
                            ForeignKey(Folder.id, ondelete='SET NULL'),
                            nullable=True)
    spam_folder = relationship('Folder', post_update=True,
                               foreign_keys=[spam_folder_id])

    trash_folder_id = Column(Integer,
                             ForeignKey(Folder.id, ondelete='SET NULL'),
                             nullable=True)
    trash_folder = relationship('Folder', post_update=True,
                                foreign_keys=[trash_folder_id])

    archive_folder_id = Column(Integer,
                               ForeignKey(Folder.id, ondelete='SET NULL'),
                               nullable=True)
    archive_folder = relationship('Folder', post_update=True,
                                  foreign_keys=[archive_folder_id])

    all_folder_id = Column(Integer,
                           ForeignKey(Folder.id, ondelete='SET NULL'),
                           nullable=True)
    all_folder = relationship('Folder', post_update=True,
                              foreign_keys=[all_folder_id])

    starred_folder_id = Column(Integer,
                               ForeignKey(Folder.id, ondelete='SET NULL'),
                               nullable=True)
    starred_folder = relationship('Folder', post_update=True,
                                  foreign_keys=[starred_folder_id])

    important_folder_id = Column(Integer,
                                 ForeignKey(Folder.id, ondelete='SET NULL'),
                                 nullable=True)
    important_folder = relationship('Folder', post_update=True,
                                    foreign_keys=[important_folder_id])

    default_calendar_id = Column(Integer,
                                 ForeignKey('calendar.id',
                                            ondelete='SET NULL',
                                            use_alter=True,
                                            name='account_ibfk_10'),
                                 nullable=True)

    _default_calendar = relationship('Calendar', post_update=True)

    @property
    def default_calendar(self):
        if not self._default_calendar:
            public_id = generate_public_id()
            new_cal = Calendar()
            new_cal.public_id = public_id
            new_cal.namespace = self.namespace
            new_cal.uid = public_id
            new_cal.read_only = False
            new_cal.name = 'default'
            new_cal.provider_name = 'inbox'
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
        if sync_host:
            self.sync_started(sync_host)
        else:
            # If a host isn't provided then start it as a new sync.
            # Setting sync_state = None makes the start condition in service.py
            # hold true, ensuring this sync is picked up and started.
            self.sync_state = None

    def sync_started(self, sync_host):
        self.sync_host = sync_host

        current_time = datetime.utcnow()

        # Never run before (vs restarting stopped/killed)
        if self.sync_state is None and (
                not self._sync_status or
                self._sync_status.get('sync_end_time') is None):
            self._sync_status['original_start_time'] = current_time

        self._sync_status['sync_start_time'] = current_time
        self._sync_status['sync_end_time'] = None
        self._sync_status['sync_error'] = None

        self.sync_state = 'running'

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
