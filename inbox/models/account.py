import os
from datetime import datetime

from sqlalchemy import (Column, BigInteger, String, DateTime, Boolean,
                        ForeignKey, Enum, inspect, bindparam, Index)
from sqlalchemy.orm import relationship
from sqlalchemy.sql.expression import false

from inbox.sqlalchemy_ext.util import JSON, MutableDict, bakery

from inbox.models.mixins import (HasPublicID, HasEmailAddress, HasRunState,
                                 HasRevisions)
from inbox.models.base import MailSyncBase
from inbox.models.calendar import Calendar
from inbox.providers import provider_info


class Account(MailSyncBase, HasPublicID, HasEmailAddress, HasRunState,
              HasRevisions):
    API_OBJECT_NAME = 'account'

    @property
    def provider(self):
        """
        A constant, unique lowercase identifier for the account provider
        (e.g., 'gmail', 'eas'). Subclasses should override this.

        """
        raise NotImplementedError

    @property
    def verbose_provider(self):
        """
        A detailed identifier for the account provider
        (e.g., 'gmail', 'office365', 'outlook').
        Subclasses may override this.

        """
        return self.provider

    @property
    def category_type(self):
        """
        Whether the account is organized by folders or labels
        ('folder'/ 'label'), depending on the provider.
        Subclasses should override this.

        """
        raise NotImplementedError

    @property
    def auth_handler(self):
        from inbox.auth.base import handler_from_provider
        return handler_from_provider(self.provider)

    @property
    def provider_info(self):
        return provider_info(self.provider, self.email_address)

    @property
    def thread_cls(self):
        from inbox.models.thread import Thread
        return Thread

    # The default phrase used when sending mail from this account.
    name = Column(String(256), nullable=False, server_default='')

    # If True, throttle initial sync to reduce resource load
    throttled = Column(Boolean, server_default=false())

    # if True we sync contacts/events/email
    # NOTE: these columns are meaningless for EAS accounts
    sync_email = Column(Boolean, nullable=False, default=True)
    sync_contacts = Column(Boolean, nullable=False, default=False)
    sync_events = Column(Boolean, nullable=False, default=False)

    last_synced_contacts = Column(DateTime, nullable=True)

    # DEPRECATED
    last_synced_events = Column(DateTime, nullable=True)

    emailed_events_calendar_id = Column(BigInteger,
                                        ForeignKey('calendar.id',
                                                   ondelete='SET NULL',
                                                   use_alter=True,
                                                   name='emailed_events_cal'),
                                        nullable=True)

    _emailed_events_calendar = relationship(
        'Calendar', post_update=True,
        foreign_keys=[emailed_events_calendar_id])

    def create_emailed_events_calendar(self):
        if not self._emailed_events_calendar:
            calname = "Emailed events"
            cal = Calendar(namespace=self.namespace,
                           description=calname,
                           uid='inbox',
                           name=calname,
                           read_only=True)
            self._emailed_events_calendar = cal

    @property
    def emailed_events_calendar(self):
        self.create_emailed_events_calendar()
        return self._emailed_events_calendar

    @emailed_events_calendar.setter
    def emailed_events_calendar(self, cal):
        self._emailed_events_calendar = cal

    sync_host = Column(String(255), nullable=True)

    # current state of this account
    state = Column(Enum('live', 'down', 'invalid'), nullable=True)

    # Based on account status, should the sync be running?
    # (Note, this is stored via a mixin.)
    # This is set to false if:
    #  - Account credentials are invalid (see mark_invalid())
    #  - External factors no longer require this account to sync
    # The value of this bit should always equal the AND value of all its
    # folders and heartbeats.

    @property
    def sync_enabled(self):
        return self.sync_should_run

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

    @property
    def sync_error(self):
        return self._sync_status.get('sync_error')

    @property
    def initial_sync_start(self):
        if len(self.folders) == 0 or \
           any([f.initial_sync_start is None for f in self.folders]):
            return None
        return min([f.initial_sync_start for f in self.folders])

    @property
    def initial_sync_end(self):
        if len(self.folders) == 0 \
           or any([f.initial_sync_end is None for f in self.folders]):
            return None
        return max([f.initial_sync_end for f in self.folders])

    @property
    def initial_sync_duration(self):
        if not self.initial_sync_start or not self.initial_sync_end:
            return None
        return (self.initial_sync_end - self.initial_sync_end).total_seconds()

    def update_sync_error(self, error=None):
        self._sync_status['sync_error'] = error

    def sync_started(self):
        """
        Record transition to started state. Should be called after the
        sync is actually started, not when the request to start it is made.

        """
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

    def enable_sync(self, sync_host=None):
        """ Tell the monitor that this account should be syncing. """
        self.sync_should_run = True
        if sync_host is not None:
            self.sync_host = sync_host

    def disable_sync(self, reason):
        """ Tell the monitor that this account should stop syncing. """
        self.sync_should_run = False
        self._sync_status['sync_disabled_reason'] = reason
        self._sync_status['sync_disabled_on'] = datetime.utcnow()
        self._sync_status['sync_disabled_by'] = os.environ.get('USER',
                                                               'unknown')

    def mark_invalid(self, reason='invalid credentials', scope='mail'):
        """
        In the event that the credentials for this account are invalid,
        update the status and sync flag accordingly. Should only be called
        after trying to re-authorize / get new token.

        """
        if scope == 'calendar':
            self.sync_events = False
        elif scope == 'contacts':
            self.sync_contacts = False
        else:
            self.disable_sync(reason)
            self.sync_state = 'invalid'

    def mark_deleted(self):
        """
        Soft-delete the account.
        """
        self.disable_sync('account deleted')

    def sync_stopped(self, reason=None):
        """
        Record transition to stopped state. Should be called after the
        sync is actually stopped, not when the request to stop it is made.

        """
        if self.sync_state == 'running':
            self.sync_state = 'stopped'
        self.sync_host = None
        self._sync_status['sync_end_time'] = datetime.utcnow()

    @classmethod
    def get(cls, id_, session):
        q = bakery(lambda session: session.query(cls))
        q += lambda q: q.filter(cls.id == bindparam('id_'))
        return q(session).params(id_=id_).first()

    @property
    def is_killed(self):
        return self.sync_state == 'killed'

    @property
    def is_running(self):
        return self.sync_state == 'running'

    @property
    def is_deleted(self):
        return self.sync_state in ('stopped', 'killed', 'invalid') and \
            self.sync_should_run is False and \
            self._sync_status.get('sync_disabled_reason') == 'account deleted'

    @property
    def should_suppress_transaction_creation(self):
        # Only version if new or the `sync_state` has changed.
        obj_state = inspect(self)
        return not (obj_state.pending or
                    inspect(self).attrs.sync_state.history.has_changes())

    discriminator = Column('type', String(16))
    __mapper_args__ = {'polymorphic_identity': 'account',
                       'polymorphic_on': discriminator}


Index('ix_account_sync_should_run_sync_host', Account.sync_should_run,
      Account.sync_host, mysql_length={'sync_host': 191})
