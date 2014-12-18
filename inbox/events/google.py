"""Provide Google Calendar events."""
import httplib2
import dateutil.parser as date_parser

from apiclient.discovery import build
from apiclient.errors import HttpError
from oauth2client.client import OAuth2Credentials
from oauth2client.client import AccessTokenRefreshError

from inbox.basicauth import (ConnectionError, ValidationError, OAuthError)
from inbox.models import Event, Calendar
from inbox.models.session import session_scope
from inbox.models.backends.gmail import GmailAccount
from inbox.auth.gmail import (OAUTH_CLIENT_ID,
                              OAUTH_CLIENT_SECRET,
                              OAUTH_ACCESS_TOKEN_URL)
from inbox.events.util import MalformedEventError, parse_datetime
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

    # A mapping from Google's status to our own
    status_map = {'accepted': 'yes', 'needsAction': 'noreply',
                  'declined': 'no', 'tentative': 'maybe'}

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
            # ignore the event. -cg3
            # TODO: Add support for reocurring events (see ways to handle
            # this generically across providers)
            if 'status' in event and event['status'] == 'cancelled':
                return None

            title = event.get('summary', '')
            description = event.get('description', None)
            location = event.get('location', None)
            all_day = False
            read_only = False
            is_owner = False

            start = event['start']
            end = event['end']
            g_recur = event.get('recurrence', None)

            recurrence = str(g_recur) if g_recur else None

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
            for attendee in event.get('attendees', []):
                g_status = attendee.get('responseStatus')
                if g_status not in GoogleEventsProvider.status_map:
                    raise MalformedEventError()
                status = GoogleEventsProvider.status_map[g_status]

                email = attendee.get('email')
                if not email:
                    raise MalformedEventError()

                name = attendee.get('displayName')

                notes = None
                guests = 0
                if 'additionalGuests' in attendee:
                    guests = attendee['additionalGuests']
                elif 'comment' in attendee:
                    notes = attendee['comment']

                participants.append({'email_address': email,
                                     'name': name,
                                     'status': status,
                                     'notes': notes,
                                     'guests': guests})

            if 'self' in event['creator']:
                is_owner = True
                read_only = False
            elif 'guestsCanModify' in event:
                read_only = False

            owner = ''
            if 'creator' in event:
                creator = event['creator']
                owner = u'{} <{}>'.format(creator['displayName'],
                                          creator['email'])

        except (KeyError, AttributeError):
            raise MalformedEventError()

        return Event(namespace_id=self.namespace_id,
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

    def create_attendee(self, participant):
        inv_status_map = {value: key for key, value in
                          GoogleEventsProvider.status_map.iteritems()}

        att = {}
        if 'name' in participant:
            att["displayName"] = participant['name']

            if 'status' in participant:
                att["responseStatus"] = inv_status_map[participant['status']]

            if 'email_address' in participant:
                att["email"] = participant['email_address']

            if 'guests' in participant:
                att["additionalGuests"] = participant['guests']

        return att

    def dump_event(self, event):
        """Convert an event db object to the Google API JSON format."""
        dump = {}
        dump["summary"] = event.title
        dump["description"] = event.description
        dump["location"] = event.location

        if not event.busy:
            # transparency: is the event shown in the gmail calendar as
            # as a solid or semi-transparent block.
            dump["transparency"] = "transparent"

        if event.all_day:
            dump["start"] = {"date": event.start.strftime('%Y-%m-%d')}
        else:
            dump["start"] = {"dateTime": event.start.isoformat('T'),
                             "timeZone": "UTC"}
            dump["end"] = {"dateTime": event.end.isoformat('T'),
                           "timeZone": "UTC"}

        if len(event.participants) > 0:
            attendees = [self.create_attendee(participant) for participant
                         in event.participants]
            dump["attendees"] = [attendee for attendee in attendees
                                 if attendee]

        return dump

    def fetch_calendar_items(self, provider_calendar_name, calendar_id,
                             sync_from_time=None):
        """Fetch the events for an individual calendar.
        parameters:
            calendarId: the google identifier for the calendar. Usually,
                username@gmail.com for the primary calendar otherwise
                random-alphanumeric-address@google.com
            calendar_id: the id of the calendar in our db.

        This function yields tuples to fetch_items. These tuples are eventually
        consumed by base_poll in inbox.sync.base_sync.
        """

        service = self._get_google_service()
        resp = service.events().list(
                calendarId=provider_calendar_name).execute()

        extra = {k: v for k, v in resp.iteritems() if k != 'items'}
        raw_events = resp['items']
        # The Google calendar API may return paginated results; make sure we
        # get all of them.
        while 'nextPageToken' in resp:
            resp = service.events().list(
                calendarId=provider_calendar_name,
                pageToken=resp['nextPageToken']).execute()
            raw_events += resp['items']

        for event in raw_events:
            yield (calendar_id, event, extra)

    def fetch_items(self, sync_from_time=None):
        """Fetch all events for all calendars. This function proxies
        fetch_calendar_items and yields the results to inbox.sync.base_sync."""

        service = self._get_google_service()
        try:
            calendars = service.calendarList().list().execute()['items']
        except AccessTokenRefreshError:
            self.log.error("Invalid user credentials given")
            with session_scope() as db_session:
                account = db_session.query(GmailAccount).get(self.account_id)
                account.sync_state = 'invalid'
                db_session.add(account)
                db_session.commit()
            raise ValidationError
        except HttpError as e:
            self.log.warn("Error retrieving events",
                          message=str(e))
            return

        for response_calendar in calendars:
            # update the calendar
            with session_scope() as db_session:
                # FIXME: refactor this to take a db session.
                calendar_id = self.get_calendar_id(
                                response_calendar['id'],
                                description=response_calendar['summary'])
                # Update calendar statuses. They may have changed.
                calendar = db_session.query(Calendar).get(calendar_id)
                if response_calendar['accessRole'] == 'reader':
                    calendar.read_only = True

                calendar_id = calendar.id

            for item in self.fetch_calendar_items(response_calendar['id'],
                         calendar_id, sync_from_time=sync_from_time):
                yield item
