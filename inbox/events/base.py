from inbox.models.session import session_scope
from inbox.models import Calendar
from inbox.sync.base_sync_provider import BaseSyncProvider
from inbox.events.util import MalformedEventError

from inbox.log import get_logger
logger = get_logger()


class BaseEventProvider(BaseSyncProvider):
    """Base class for event providers"""

    def __init__(self, account_id):
        self.account_id = account_id
        self.log = logger.new(account_id=account_id, component='event sync',
                              provider=self.PROVIDER_NAME)

    def get_calendar_id(self, name, description=None):
        calendar_id = None
        with session_scope() as db_session:
            cal = db_session.query(Calendar). \
                filter_by(account_id=self.account_id,
                          provider_name=self.PROVIDER_NAME,
                          name=name).first()
            if not cal:
                cal = Calendar(account_id=self.account_id,
                               provider_name=self.PROVIDER_NAME,
                               name=name)
                db_session.add(cal)
                db_session.commit()
            calendar_id = cal.id

            # update the description if appropriate
            if cal.description != description:
                cal.description = description
                db_session.commit()

        return calendar_id

    def get_items(self, sync_from_time=None):
        """Fetches and parses fresh event data.

        Parameters
        ----------
        sync_from_time: str, optional
            A time in ISO 8601 format: If not None, fetch data for calendars
            that have been updated since this time. Otherwise fetch all
            calendar data.

        Yields
        ------
        [..models.tables.base.Event]
            List of events that have been updated since the last account sync.
        """
        events = []
        for calendar_id, p_event, extra in self.fetch_items(sync_from_time):
            try:
                new_event = self.parse_event(p_event, extra)
                if new_event:
                    new_event.calendar_id = calendar_id
                    events.append(new_event)
            except MalformedEventError:
                self.log.warning('Malformed event', _event=p_event)

        return events

    def fetch_items(self, sync_from_time=None):
        """Generator that yields items from the provider.

        This function is called by the base_sync to obtain individual items
        from each provider. It yields a tuple of (calendar_id, event, extra)
        detailed below. This class then passes the provider-specific 'event'
        and the 'extra' argument to the 'parse_event' function described below.

        Parameters
        ----------
        sync_from_time: str, optional
            Same parameter as passed to the 'get_items' function.

        Yields
        ------
        (calendar_id, event, extra)
            'calendar_id' is an id for the ..models.tables.base.Calendar for
            which the event belongs.
            'event' is a provider specific event that is passed to the
            parse_event function.
            'extra' is an extra parameter that is also passed to the
            parse_event function for provider-specific event parsing.
        """
        raise NotImplementedError

    def parse_event(self, provider_event, extra):
        """Parses provider-specific event into ..models.tables.base.Event

        This function is called by the BaseEventProvider for each of the events
        that is yielded by the 'fetch_items' function. It parses the
        provider-specific 'event' into a ..models.table.base.Event.

        Parameters
        ----------
        provider_event
            provider-specific event yielded by the 'fetch_items' function
        extra
            extra parameter yielded by the 'fetch_items' function


        Returns
        -------
        ..models.tables.base.Event
            Event object representing the provider-specific event

        Throws
        ------
        MalformedEventError
            Exception thrown when the provider-specific event cannot be parsed.
        """
        raise NotImplementedError
