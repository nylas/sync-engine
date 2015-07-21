from datetime import datetime, timedelta

from inbox.log import get_logger
logger = get_logger()

from inbox.basicauth import AccessNotEnabledError, OAuthError
from inbox.config import config
from inbox.sync.base_sync import BaseSyncMonitor
from inbox.models import Event, Calendar
from inbox.models.event import RecurringEvent, RecurringEventOverride
from inbox.util.debug import bind_context
from inbox.models.session import session_scope

from inbox.models.account import Account

from inbox.events.recurring import link_events
from inbox.events.google import GoogleEventsProvider


EVENT_SYNC_FOLDER_ID = -2
EVENT_SYNC_FOLDER_NAME = 'Events'
POLL_FREQUENCY = config.get('CALENDAR_POLL_FREQUENCY', 300)

MAX_TIME_WITHOUT_SYNC = timedelta(seconds=3600)


class EventSync(BaseSyncMonitor):
    """Per-account event sync engine."""
    def __init__(self, email_address, provider_name, account_id, namespace_id,
                 poll_frequency=POLL_FREQUENCY):
        bind_context(self, 'eventsync', account_id)
        # Only Google for now, can easily parametrize by provider later.
        self.provider = GoogleEventsProvider(account_id, namespace_id)

        BaseSyncMonitor.__init__(self,
                                 account_id,
                                 namespace_id,
                                 email_address,
                                 EVENT_SYNC_FOLDER_ID,
                                 EVENT_SYNC_FOLDER_NAME,
                                 provider_name,
                                 poll_frequency=poll_frequency,
                                 scope='calendar')

    def sync(self):
        """Query a remote provider for updates and persist them to the
        database. This function runs every `self.poll_frequency`.
        """
        self.log.info('syncing events')

        try:
            deleted_uids, calendar_changes = self.provider.sync_calendars()
        except AccessNotEnabledError:
            self.log.warning(
                'Access to provider calendar API not enabled; bypassing sync')
            return
        with session_scope() as db_session:
            handle_calendar_deletes(self.namespace_id, deleted_uids,
                                    self.log, db_session)
            calendar_uids_and_ids = handle_calendar_updates(self.namespace_id,
                                                            calendar_changes,
                                                            self.log,
                                                            db_session)
            db_session.commit()

        for (uid, id_) in calendar_uids_and_ids:
            # Get a timestamp before polling, so that we don't subsequently
            # miss remote updates that happen while the poll loop is executing.
            sync_timestamp = datetime.utcnow()
            with session_scope() as db_session:
                last_sync = db_session.query(Calendar.last_synced).filter(
                    Calendar.id == id_).scalar()

            event_changes = self.provider.sync_events(
                uid, sync_from_time=last_sync)

            with session_scope() as db_session:
                handle_event_updates(self.namespace_id, id_, event_changes,
                                     self.log, db_session)
                cal = db_session.query(Calendar).get(id_)
                cal.last_synced = sync_timestamp
                db_session.commit()


def handle_calendar_deletes(namespace_id, deleted_calendar_uids, log,
                            db_session):
    """Delete any local Calendar rows with uid in `deleted_calendar_uids`. This
    delete cascades to associated events (if the calendar is gone, so are all
    of its events)."""
    deleted_count = 0
    for uid in deleted_calendar_uids:
        local_calendar = db_session.query(Calendar).filter(
            Calendar.namespace_id == namespace_id,
            Calendar.uid == uid).first()
        if local_calendar is not None:
            # Cascades to associated events via SQLAlchemy 'delete' cascade
            db_session.delete(local_calendar)
            deleted_count += 1
    log.info('deleted calendars', deleted=deleted_count)


def handle_calendar_updates(namespace_id, calendars, log, db_session):
    """Persists new or updated Calendar objects to the database."""
    ids_ = []
    added_count = 0
    updated_count = 0
    for calendar in calendars:
        assert calendar.uid is not None, 'Got remote item with null uid'

        local_calendar = db_session.query(Calendar).filter(
            Calendar.namespace_id == namespace_id,
            Calendar.uid == calendar.uid).first()

        if local_calendar is not None:
            local_calendar.update(calendar)
            updated_count += 1
        else:
            local_calendar = Calendar(namespace_id=namespace_id)
            local_calendar.update(calendar)
            db_session.add(local_calendar)
            db_session.flush()
            added_count += 1

        ids_.append((local_calendar.uid, local_calendar.id))

    log.info('synced added and updated calendars', added=added_count,
             updated=updated_count)
    return ids_


def handle_event_updates(namespace_id, calendar_id, events, log, db_session):
    """Persists new or updated Event objects to the database."""
    added_count = 0
    updated_count = 0
    for event in events:
        assert event.uid is not None, 'Got remote item with null uid'

        # Note: we could bulk-load previously existing events instead of
        # loading them one-by-one. This would make the first sync faster, and
        # probably not really affect anything else.
        local_event = db_session.query(Event).filter(
            Event.namespace_id == namespace_id,
            Event.calendar_id == calendar_id,
            Event.uid == event.uid).first()

        if local_event is not None:
            # We also need to mark all overrides as cancelled if we're
            # cancelling a recurring event. However, note the original event
            # may not itself be recurring (recurrence may have been added).
            if isinstance(local_event, RecurringEvent) and \
                    event.status == 'cancelled' and \
                    local_event.status != 'cancelled':
                    for override in local_event.overrides:
                        override.status = 'cancelled'

            merged_participants = local_event.\
                _partial_participants_merge(event)

            local_event.update(event)

            # We have to do this mumbo-jumbo because MutableList does
            # not register changes to nested elements.
            local_event.participants = []
            for participant in merged_participants:
                local_event.participants.append(participant)

            updated_count += 1
        else:
            local_event = event
            local_event.namespace_id = namespace_id
            local_event.calendar_id = calendar_id
            db_session.add(local_event)
            added_count += 1

        # If we just updated/added a recurring event or override, make sure
        # we link it to the right master event.
        if isinstance(event, RecurringEvent) or \
                isinstance(event, RecurringEventOverride):
            db_session.flush()
            link_events(db_session, event)

    log.info('synced added and updated events',
             calendar_id=calendar_id,
             added=added_count,
             updated=updated_count)


class GoogleEventSync(EventSync):

    def sync(self):
        """Query a remote provider for updates and persist them to the
        database. This function runs every `self.poll_frequency`.

        This function also handles refreshing google's push notifications
        if they are enabled for this account. Sync is bypassed if we are
        currently subscribed to push notificaitons and haven't heard anything
        new from Google.
        """
        self.log.info('syncing events')

        try:
            self._refresh_gpush_subscriptions()
        except AccessNotEnabledError:
            self.log.warning(
                'Access to provider calendar API not enabled; '
                'cannot sign up for push notifications')
        except OAuthError:
            # Not enough of a reason to halt the sync!
            self.log.warning(
                'Not authorized to set up push notifications for account'
                '(Safe to ignore this message if not recurring.)',
                account_id=self.account_id)

        try:
            self._sync_data()
        except AccessNotEnabledError:
            self.log.warning(
                'Access to provider calendar API not enabled; '
                'bypassing sync')

    def _refresh_gpush_subscriptions(self):

        with session_scope() as db_session:
            account = db_session.query(Account).get(self.account_id)

            if not self.provider.push_notifications_enabled(account):
                return

            if account.needs_new_calendar_list_watch():
                expir = self.provider.watch_calendar_list(account)
                if expir is not None:
                    account.new_calendar_list_watch(expir)

            cals_to_update = (cal for cal in account.namespace.calendars
                              if cal.needs_new_watch())
            for cal in cals_to_update:
                expir = self.provider.watch_calendar(account, cal)
                if expir is not None:
                    cal.new_event_watch(expir)

    def _sync_data(self):
        with session_scope() as db_session:

            account = db_session.query(Account).get(self.account_id)
            if account.should_update_calendars(MAX_TIME_WITHOUT_SYNC):
                self._sync_calendar_list(account, db_session)

            stale_calendars = (
                cal for cal in account.namespace.calendars
                if cal.should_update_events(MAX_TIME_WITHOUT_SYNC)
            )
            for cal in stale_calendars:
                self._sync_calendar(cal, db_session)

    def _sync_calendar_list(self, account, db_session):
        sync_timestamp = datetime.utcnow()
        deleted_uids, calendar_changes = self.provider.sync_calendars()

        handle_calendar_deletes(self.namespace_id, deleted_uids,
                                self.log, db_session)
        handle_calendar_updates(self.namespace_id,
                                calendar_changes,
                                self.log,
                                db_session)

        account.last_calendar_list_sync = sync_timestamp
        db_session.commit()

    def _sync_calendar(self, calendar, db_session):
        sync_timestamp = datetime.utcnow()
        event_changes = self.provider.sync_events(
            calendar.uid, sync_from_time=calendar.last_synced)

        handle_event_updates(self.namespace_id, calendar.id,
                             event_changes, self.log, db_session)
        calendar.last_synced = sync_timestamp
        db_session.commit()
