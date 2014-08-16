"""Provide Google Calendar events."""

import httplib2
import dateutil.parser as date_parser

from apiclient.discovery import build
from oauth2client.client import OAuth2Credentials
from oauth2client.client import AccessTokenRefreshError

from inbox.log import get_logger
logger = get_logger()
from inbox.basicauth import ConnectionError, ValidationError
from inbox.oauth import OAuthError
from inbox.models.session import session_scope
from inbox.models import Event
from inbox.models.backends.gmail import GmailAccount
from inbox.auth.gmail import (OAUTH_CLIENT_ID,
                              OAUTH_CLIENT_SECRET,
                              OAUTH_ACCESS_TOKEN_URL)
from inbox.sync.base_sync_provider import BaseSyncProvider
from inbox.events.util import MalformedEventError, parse_datetime

SOURCE_APP_NAME = 'InboxApp Calendar Sync Engine'


class GoogleEventsProvider(BaseSyncProvider):
    """A utility class to fetch and parse Google calendar data for the
    specified account using the Google Calendar API.

    Parameters
    ----------
    db_session: sqlalchemy.orm.session.Session
        Database session.

    account_id: GmailAccount.id
        The user account for which to fetch event data.

    Attributes
    ----------
    google_client: gdata.calendar.client.CalendarClient
        Google API client to do the actual data fetching.
    log: logging.Logger
        Logging handler.
    """
    PROVIDER_NAME = 'google'

    def __init__(self, account_id):
        self.account_id = account_id
        self.log = logger.new(account_id=account_id, component='event sync',
                              provider=self.PROVIDER_NAME)

    def _get_google_service(self):
        """Return the Google API client."""
        # TODO(emfree) figure out a better strategy for refreshing OAuth
        # credentials as needed
        with session_scope() as db_session:
            try:
                account = db_session.query(GmailAccount).get(self.account_id)
                client_id = account.client_id or OAUTH_CLIENT_ID
                client_secret = (account.client_secret or
                                 OAUTH_CLIENT_SECRET)

                self.email = account.email_address

                access_token = account.access_token
                refresh_token = account.refresh_token
                expiry = account.access_expiry

                credentials = OAuth2Credentials(
                    access_token,
                    client_id,
                    client_secret,
                    refresh_token,
                    expiry,
                    OAUTH_ACCESS_TOKEN_URL,
                    SOURCE_APP_NAME)

                http = httplib2.Http()
                http = credentials.authorize(http)

                service = build(serviceName='calendar',
                                version='v3',
                                http=http)

                return service

            except OAuthError:
                self.log.error('Invalid user credentials given')
                account.sync_state = 'invalid'
                db_session.add(account)
                db_session.commit()
                raise ValidationError
            except ConnectionError:
                self.log.error('Connection error')
                account.sync_state = 'connerror'
                db_session.add(account)
                db_session.commit()
                raise ConnectionError

    def _parse_event(self, cal_info, event):
        """Constructs a Calendar object from a Google calendar entry.

        Parameters
        ----------
        google_calendar: gdata.calendar.entry.CalendarEntry
            The Google calendar entry to parse.

        Returns
        -------
        ..models.tables.base.Calendar
            A corresponding Inbox Calendar instance.

        Raises
        ------
        AttributeError
           If the calendar data could not be parsed correctly.
        """

        try:
            uid = str(event['id'])

            # The entirety of the raw event data in json representation.
            raw_data = str(event)

            # 'cancelled' events signify those instances within a series
            # that have been cancelled (for that given series). As such,
            # since full support for dealing with single instances within
            # a reocurring event series is not added, right now we just
            # treat this event as 'malformed'. -cg3
            # TODO: Add support for reocurring events (see ways to handle
            # this generically across providers)
            if 'status' in event and event['status'] == 'cancelled':
                raise MalformedEventError()

            subject = event.get('summary', '')[0:1023]
            body = event.get('description', None)
            location = event.get('location', None)
            if location:
                location = location[0:254]
            all_day = False
            locked = True

            start = event['start']
            end = event['end']
            recurrence = str(event.get('recurrence', None))

            busy = event.get('transparency', True)
            if busy == 'transparent':
                busy = False

            reminders = []
            if 'dateTime' in start:
                if event['reminders']['useDefault']:
                    reminder_source = cal_info['defaultReminders']
                elif 'overrides' in event['reminders']:
                    reminder_source = event['reminders']['overrides']
                else:
                    reminder_source = None

                if reminder_source:
                    for reminder in reminder_source:
                        reminders.append(reminder['minutes'])

                start = parse_datetime(start['dateTime'])
                end = parse_datetime(end['dateTime'])
            else:
                start = date_parser.parse(start['date'])
                end = date_parser.parse(end['date'])
                all_day = True

            reminders = str(reminders)

            if 'self' in event['creator']:
                locked = False
            elif 'guestsCanModify' in event:
                locked = False

            time_zone = cal_info['timeZone']
            time_zone = 0  # FIXME: this ain't right -cg3

        except (KeyError, AttributeError):
            raise MalformedEventError()

        return Event(account_id=self.account_id,
                     uid=uid,
                     provider_name=self.PROVIDER_NAME,
                     raw_data=raw_data,
                     subject=subject,
                     body=body,
                     location=location,
                     reminders=reminders,
                     recurrence=recurrence,
                     start=start,
                     end=end,
                     busy=busy,
                     all_day=all_day,
                     locked=locked,
                     time_zone=time_zone,
                     source='remote')

    def get_items(self, sync_from_time=None, max_results=100000):
        """Fetches and parses fresh event data.

        Parameters
        ----------
        sync_from_time: str, optional
            A time in ISO 8601 format: If not None, fetch data for calendars
            that have been updated since this time. Otherwise fetch all
            calendar data.
        max_results: int, optional
            The maximum number of calendar entries to fetch.

        Yields
        ------
        ..models.tables.base.Events
            The events that have been updated since the last account sync.
        """
        service = self._get_google_service()
        try:
            resp = service.events().list(calendarId=self.email).execute()
        except AccessTokenRefreshError:
            self.log.error('Invalid user credentials given')
            with session_scope() as db_session:
                account = db_session.query(GmailAccount).get(self.account_id)
                account.sync_state = 'invalid'
                db_session.add(account)
                db_session.commit()
            raise ValidationError

        events = []
        for response_event in resp['items']:
            try:
                events.append(self._parse_event(resp, response_event))
            except MalformedEventError:
                self.log.warning('Malformed event',
                                 google_event=response_event)

        return events
