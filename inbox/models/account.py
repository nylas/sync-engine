import os
import traceback
from datetime import datetime

from sqlalchemy import (Column, BigInteger, String, DateTime, Boolean,
                        ForeignKey, Enum, inspect, bindparam, Index, event)
from sqlalchemy.orm import relationship
from sqlalchemy.orm.session import Session
from sqlalchemy.sql.expression import false

from inbox.config import config
from inbox.sqlalchemy_ext.util import JSON, MutableDict, bakery

from inbox.models.mixins import (HasPublicID, HasEmailAddress, HasRunState,
                                 HasRevisions, UpdatedAtMixin,
                                 DeletedAtMixin)
from inbox.models.base import MailSyncBase
from inbox.models.calendar import Calendar
from inbox.scheduling.event_queue import EventQueue
from inbox.providers import provider_info
from nylas.logging.sentry import log_uncaught_errors
from nylas.logging import get_logger
log = get_logger()


# Note, you should never directly create Account objects. Instead you
# should use objects that inherit from this, such as GenericAccount or
# GmailAccount

class Account(MailSyncBase, HasPublicID, HasEmailAddress, HasRunState,
              HasRevisions, UpdatedAtMixin, DeletedAtMixin):
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
        return provider_info(self.provider)

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
    desired_sync_host = Column(String(255), nullable=True)

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
                 sync_host=self.sync_host,
                 desired_sync_host=self.desired_sync_host)
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
        if error is None:
            self._sync_status['sync_error'] = None
        else:
            error_obj = {
                'message': str(error.message)[:3000],
                'exception': "".join(traceback.format_exception_only(type(error), error))[:500],
                'traceback': traceback.format_exc(20)[:3000]}

            self._sync_status['sync_error'] = error_obj

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
        self._sync_status['sync_disabled_reason'] = None
        self._sync_status['sync_disabled_on'] = None
        self._sync_status['sync_disabled_by'] = None

        self.sync_state = 'running'

    def enable_sync(self):
        """ Tell the monitor that this account should be syncing. """
        self.sync_should_run = True

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

    def mark_for_deletion(self):
        """
        Mark account for deletion
        """
        self.disable_sync('account deleted')
        self.sync_state = 'stopped'
        # Commit this to prevent race conditions
        inspect(self).session.commit()

    def unmark_for_deletion(self):
        self.enable_sync()
        self._sync_status = {}
        self.sync_state = 'running'
        inspect(self).session.commit()

    def sync_stopped(self, requesting_host):
        """
        Record transition to stopped state. Should be called after the
        sync is actually stopped, not when the request to stop it is made.

        """
        if requesting_host == self.sync_host:
            # Perform a compare-and-swap before updating these values.
            # Only if the host requesting to update the account.sync_* attributes
            # here still owns the account sync (i.e is account.sync_host),
            # the request can proceed.
            self.sync_host = None
            if self.sync_state == 'running':
                self.sync_state = 'stopped'
            self._sync_status['sync_end_time'] = datetime.utcnow()
            return True
        return False

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
    def is_marked_for_deletion(self):
        return self.sync_state in ('stopped', 'killed', 'invalid') and \
            self.sync_should_run is False and \
            self._sync_status.get('sync_disabled_reason') == 'account deleted'

    @property
    def should_suppress_transaction_creation(self):
        # Only version if new or the `sync_state` has changed.
        obj_state = inspect(self)
        return not (obj_state.pending or
                    inspect(self).attrs.sync_state.history.has_changes())

    @property
    def server_settings(self):
        return None

    def get_raw_message_contents(self, message):
        # Get the raw contents of a message. We do this differently
        # for every backend (Gmail, IMAP, EAS), and the best way
        # to do this across repos is to make it a method of the
        # account class.
        raise NotImplementedError

    discriminator = Column('type', String(16))
    __mapper_args__ = {'polymorphic_identity': 'account',
                       'polymorphic_on': discriminator}


def should_send_event(obj):
    if not isinstance(obj, Account):
        return False
    inspected_obj = inspect(obj)
    hist = inspected_obj.attrs.sync_host.history
    if hist.has_changes():
        return True
    hist = inspected_obj.attrs.desired_sync_host.history
    if hist.has_changes():
        return True
    hist = inspected_obj.attrs.sync_should_run.history
    return hist.has_changes()


def already_registered_listener(obj):
    return getattr(obj, '_listener_state', None) is not None


def update_listener_state(obj):
    obj._listener_state['sync_should_run'] = obj.sync_should_run
    obj._listener_state['sync_host'] = obj.sync_host
    obj._listener_state['desired_sync_host'] = obj.desired_sync_host
    obj._listener_state['sent_event'] = False


@event.listens_for(Session, "after_flush")
def after_flush(session, flush_context):
    from inbox.mailsync.service import shared_sync_event_queue_for_zone, SYNC_EVENT_QUEUE_NAME

    def send_migration_events(obj_state):
        def f(session):
            if obj_state['sent_event']:
                return

            id = obj_state['id']
            sync_should_run = obj_state['sync_should_run']
            sync_host = obj_state['sync_host']
            desired_sync_host = obj_state['desired_sync_host']

            try:
                if sync_host is not None:
                    # Somebody is actively syncing this Account, so notify them if
                    # they should give up the Account.
                    if not sync_should_run or (sync_host != desired_sync_host and desired_sync_host is not None):
                        queue_name = SYNC_EVENT_QUEUE_NAME.format(sync_host)
                        log.info("Sending 'migrate_from' event for Account",
                                 account_id=id, queue_name=queue_name)
                        EventQueue(queue_name).send_event({'event': 'migrate_from', 'id': id})
                    return

                if not sync_should_run:
                    # We don't need to notify anybody because the Account is not
                    # actively being synced (sync_host is None) and sync_should_run is False,
                    # so just return early.
                    return

                if desired_sync_host is not None:
                    # Nobody is actively syncing the Account, and we have somebody
                    # who wants to sync this Account, so notify them.
                    queue_name = SYNC_EVENT_QUEUE_NAME.format(desired_sync_host)
                    log.info("Sending 'migrate_to' event for Account",
                             account_id=id, queue_name=queue_name)
                    EventQueue(queue_name).send_event({'event': 'migrate_to', 'id': id})
                    return

                # Nobody is actively syncing the Account, and nobody in particular
                # wants to sync the Account so notify the shared queue.
                shared_queue = shared_sync_event_queue_for_zone(config.get('ZONE'))
                log.info("Sending 'migrate' event for Account",
                         account_id=id, queue_name=shared_queue.queue_name)
                shared_queue.send_event({'event': 'migrate', 'id': id})
                obj_state['sent_event'] = True
            except:
                log_uncaught_errors(log, account_id=id, sync_host=sync_host,
                                    desired_sync_host=desired_sync_host)
        return f

    for obj in session.new:
        if isinstance(obj, Account):
            if already_registered_listener(obj):
                update_listener_state(obj)
            else:
                obj._listener_state = {'id': obj.id}
                update_listener_state(obj)
                event.listen(session,
                             'after_commit',
                             send_migration_events(obj._listener_state))

    for obj in session.dirty:
        if not session.is_modified(obj):
            continue
        if should_send_event(obj):
            if already_registered_listener(obj):
                update_listener_state(obj)
            else:
                obj._listener_state = {'id': obj.id}
                update_listener_state(obj)
                event.listen(session,
                             'after_commit',
                             send_migration_events(obj._listener_state))


Index('ix_account_sync_should_run_sync_host', Account.sync_should_run,
      Account.sync_host, mysql_length={'sync_host': 191})
