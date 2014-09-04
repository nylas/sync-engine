"""Provide Google Calendar events."""

import httplib2
import dateutil.parser as date_parser

from apiclient.discovery import build
from oauth2client.client import OAuth2Credentials
from oauth2client.client import AccessTokenRefreshError

from inbox.basicauth import ConnectionError, ValidationError
from inbox.oauth import OAuthError
from inbox.models import Event, Participant
from inbox.models.session import session_scope
from inbox.models.backends.gmail import GmailAccount
from inbox.auth.gmail import (OAUTH_CLIENT_ID,
                              OAUTH_CLIENT_SECRET,
                              OAUTH_ACCESS_TOKEN_URL)
from inbox.events.util import MalformedEventError, parse_datetime
from inbox.models.event import TITLE_MAX_LEN, LOCATION_MAX_LEN
from inbox.events.base import BaseEventProvider

SOURCE_APP_NAME = 'InboxApp Calendar Sync Engine'


# Silence the stupid Google API client logger
import logging
apiclient_logger = logging.getLogger('apiclient.discovery')
apiclient_logger.setLevel(40)


class GoogleEventsProvider(BaseEventProvider):
    """A utility class to fetch and parse Google calendar data for the
    specified account using the Google Calendar API.

    Parameters
    ----------
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

    def _get_google_service(self):
        """Return the Google API client."""
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

    def parse_event(self, event, cal_info):
        """Constructs an Event object from a Google calendar entry.

        Parameters
        ----------
        event: gdata.calendar.entry.CalendarEntry
            The Google calendar entry to parse.

        Returns
        -------
        ..models.tables.base.Event
            A corresponding Inbox Event instance.

        Raises
        ------
        MalformedEventError
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

            title = event.get('summary', '')[:TITLE_MAX_LEN]
            description = event.get('description', None)
            location = event.get('location', None)
            if location:
                location = location[:LOCATION_MAX_LEN]
            all_day = False
            read_only = True
            is_owner = False

            start = event['start']
            end = event['end']
            g_reccur = event.get('recurrence', None)
            recurrence = str(g_reccur) if g_reccur else None

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

                try:
                    start = parse_datetime(start['dateTime'])
                    end = parse_datetime(end['dateTime'])
                except TypeError:
                    self.log.error('Invalid start: {} or end: {}'
                                   .format(start['dateTime'],
                                           end['dateTime']))
                    raise MalformedEventError()

            else:
                start = date_parser.parse(start['date'])
                end = date_parser.parse(end['date'])
                all_day = True

            reminders = str(reminders)

            # Convert google's notion of status into our own
            participants = []
            status_map = {'accepted': 'yes', 'needsAction': 'noreply',
                          'declined': 'no', 'tentative': 'maybe'}
            for attendee in event.get('attendees', []):
                g_status = attendee.get('responseStatus')
                if g_status not in status_map:
                    raise MalformedEventError()
                status = status_map[g_status]

                email = attendee.get('email')
                if not email:
                    raise MalformedEventError()

                name = attendee.get('displayName')

                notes = None
                if 'additionalGuests' in attendee:
                    notes = "Guests: {}".format(attendee['additionalGuests'])
                    if 'comment' in attendee:
                        notes += " Notes: {}".format(attendee['comment'])
                elif 'comment' in attendee:
                    notes = "Notes: {}".format(attendee['comment'])

                participants.append(Participant(email_address=email,
                                                name=name,
                                                status=status,
                                                notes=notes))

            if 'self' in event['creator']:
                is_owner = True
                read_only = False
            elif 'guestsCanModify' in event:
                read_only = False

            owner = "{} <{}>".format(event['creator']['displayName'],
                                     event['creator']['email'])

        except (KeyError, AttributeError):
            raise MalformedEventError()

        return Event(account_id=self.account_id,
                     uid=uid,
                     provider_name=self.PROVIDER_NAME,
                     raw_data=raw_data,
                     title=title,
                     description=description,
                     location=location,
                     reminders=reminders,
                     recurrence=recurrence,
                     start=start,
                     end=end,
                     owner=owner,
                     is_owner=is_owner,
                     busy=busy,
                     all_day=all_day,
                     read_only=read_only,
                     source='remote',
                     participants=participants)

    def fetch_items(self, sync_from_time=None):
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

        # Make sure we have a calendar associated with these events
        description = resp.get('description')
        calendar_id = self.get_calendar_id(resp['summary'], description)

        for response_event in resp['items']:
            yield (calendar_id, response_event, resp)
