"""Provide Google Calendar events."""
import datetime
import json
import random
import urllib
import gevent
import requests
import uuid

from inbox.auth.oauth import OAuthRequestsWrapper
from inbox.basicauth import AccessNotEnabledError
from inbox.config import config
from nylas.logging import get_logger
from inbox.models import Calendar, Account
from inbox.models.event import Event, EVENT_STATUSES
from inbox.models.session import session_scope
from inbox.models.backends.gmail import g_token_manager
from inbox.events.util import (google_to_event_time, parse_google_time,
                               parse_datetime, CalendarSyncResponse)


log = get_logger()
CALENDARS_URL = 'https://www.googleapis.com/calendar/v3/users/me/calendarList'
STATUS_MAP = {'accepted': 'yes', 'needsAction': 'noreply',
              'declined': 'no', 'tentative': 'maybe'}

URL_PREFIX = config.get('API_URL', 'https://api.nylas.com')

PUSH_ENABLED_CLIENT_IDS = config.get('PUSH_ENABLED_CLIENT_IDS', [])

CALENDAR_LIST_WEBHOOK_URL = URL_PREFIX + '/w/calendar_list_update/{}'
EVENTS_LIST_WEHOOK_URL = URL_PREFIX + '/w/calendar_update/{}'

WATCH_CALENDARS_URL = CALENDARS_URL + '/watch'
WATCH_EVENTS_URL = \
    'https://www.googleapis.com/calendar/v3/calendars/{}/events/watch'


class GoogleEventsProvider(object):
    """
    A utility class to fetch and parse Google calendar data for the
    specified account using the Google Calendar API.
    """

    def __init__(self, account_id, namespace_id):
        self.account_id = account_id
        self.namespace_id = namespace_id
        self.log = log.new(account_id=account_id)

        # A hash to store whether a calendar is read-only or not.
        # This is a bit of a hack because this isn't exposed at the event level
        # by the Google Event API.
        self.calendars_table = {}

    def sync_calendars(self):
        """ Fetches data for the user's calendars.
        Returns
        -------
        CalendarSyncResponse
        """

        deletes = []
        updates = []
        items = self._get_raw_calendars()
        for item in items:
            if item.get('deleted'):
                deletes.append(item['id'])
            else:
                cal = parse_calendar_response(item)
                self.calendars_table[item['id']] = cal.read_only
                updates.append(cal)

        return CalendarSyncResponse(deletes, updates)

    def sync_events(self, calendar_uid, sync_from_time=None):
        """ Fetches event data for an individual calendar.

        Parameters
        ----------
        calendar_uid: the google identifier for the calendar.
            Usually username@gmail.com for the primary calendar, otherwise
            random-alphanumeric-address@*.google.com
        sync_from_time: datetime
            Only sync events which have been added or changed since this time.
            Note that if this is too far in the past, the Google calendar API
            may return an HTTP 410 error, in which case we transparently fetch
            all event data.

        Returns
        -------
        A list of uncommited Event instances.
        """
        updates = []
        items = self._get_raw_events(calendar_uid, sync_from_time)
        read_only_calendar = self.calendars_table.get(calendar_uid, True)
        for item in items:
            updates.append(parse_event_response(item, read_only_calendar))

        return updates

    def _get_raw_calendars(self):
        """Gets raw data for the user's calendars."""
        return self._get_resource_list(CALENDARS_URL)

    def _get_raw_events(self, calendar_uid, sync_from_time=None):
        """ Gets raw event data for the given calendar.

        Parameters
        ----------
        calendar_uid: string
            Google's ID for the calendar we're getting events on.
        sync_from_time: datetime, optional
            If given, only fetch data for events that have changed since this
            time.

        Returns
        -------
        list of dictionaries representing JSON.
        """
        if sync_from_time is not None:
            # Note explicit offset is required by Google calendar API.
            sync_from_time = datetime.datetime.isoformat(sync_from_time) + 'Z'

        url = 'https://www.googleapis.com/calendar/v3/' \
              'calendars/{}/events'.format(urllib.quote(calendar_uid))
        try:
            return self._get_resource_list(url, updatedMin=sync_from_time)
        except requests.exceptions.HTTPError as exc:
            if exc.response.status_code == 410:
                # The calendar API may return 410 if you pass a value for
                # updatedMin that's too far in the past. In that case, refetch
                # all events.
                return self._get_resource_list(url)
            else:
                raise

    def _get_access_token(self, force_refresh=False):
        with session_scope(self.namespace_id) as db_session:
            acc = db_session.query(Account).get(self.account_id)
            # This will raise OAuthError if OAuth access was revoked. The
            # BaseSyncMonitor loop will catch this, clean up, and exit.
            return g_token_manager.get_token_for_calendars(
                acc, force_refresh=force_refresh)

    def _get_resource_list(self, url, **params):
        """Handles response pagination."""
        token = self._get_access_token()
        items = []
        next_page_token = None
        params['showDeleted'] = True
        while True:
            if next_page_token is not None:
                params['pageToken'] = next_page_token
            try:
                r = requests.get(url, params=params,
                                 auth=OAuthRequestsWrapper(token))
                r.raise_for_status()
                data = r.json()
                items += data['items']
                next_page_token = data.get('nextPageToken')
                if next_page_token is None:
                    return items

            except requests.exceptions.SSLError:
                self.log.warning(
                    'SSLError making Google Calendar API requestl retrying',
                    url=url, exc_info=True)
                gevent.sleep(30 + random.randrange(0, 60))
                continue
            except requests.HTTPError:
                self.log.warning(
                    'HTTP error making Google Calendar API request', url=r.url,
                    response=r.content, status=r.status_code)
                if r.status_code == 401:
                    self.log.warning(
                        'Invalid access token; refreshing and retrying',
                        url=r.url, response=r.content, status=r.status_code)
                    token = self._get_access_token(force_refresh=True)
                    continue
                elif r.status_code in (500, 503):
                    log.warning('Backend error in calendar API; retrying')
                    gevent.sleep(30 + random.randrange(0, 60))
                    continue
                elif r.status_code == 403:
                    try:
                        reason = r.json()['error']['errors'][0]['reason']
                    except (KeyError, ValueError):
                        log.error("Couldn't parse API error response",
                                  response=r.content, status=r.status_code)
                        r.raise_for_status()
                    if reason == 'userRateLimitExceeded':
                        log.warning('API request was rate-limited; retrying')
                        gevent.sleep(30 + random.randrange(0, 60))
                        continue
                    elif reason == 'accessNotConfigured':
                        log.warning('API not enabled; returning empty result')
                        raise AccessNotEnabledError()
                # Unexpected error; raise.
                raise

    def _make_event_request(self, method, calendar_uid, event_uid=None,
                            **kwargs):
        """ Makes a POST/PUT/DELETE request for a particular event. """
        event_uid = event_uid or ''
        url = 'https://www.googleapis.com/calendar/v3/' \
              'calendars/{}/events/{}'.format(urllib.quote(calendar_uid),
                                              urllib.quote(event_uid))
        token = self._get_access_token()
        response = requests.request(method, url,
                                    auth=OAuthRequestsWrapper(token),
                                    **kwargs)
        return response

    def create_remote_event(self, event, **kwargs):
        data = _dump_event(event)
        params = {}

        if kwargs.get('notify_participants') is True:
            params["sendNotifications"] = "true"
        else:
            params["sendNotifications"] = "false"

        response = self._make_event_request('post', event.calendar.uid,
                                            json=data, params=params)

        # All non-200 statuses are considered errors
        response.raise_for_status()
        return response.json()

    def update_remote_event(self, event, **kwargs):
        data = _dump_event(event)
        params = {}

        if kwargs.get('notify_participants') is True:
            params["sendNotifications"] = "true"
        else:
            params["sendNotifications"] = "false"

        response = self._make_event_request('put', event.calendar.uid,
                                            event.uid, json=data,
                                            params=params)

        # All non-200 statuses are considered errors
        response.raise_for_status()

    def delete_remote_event(self, calendar_uid, event_uid, **kwargs):
        params = {}

        if kwargs.get('notify_participants') is True:
            params["sendNotifications"] = "true"
        else:
            params["sendNotifications"] = "false"

        response = self._make_event_request('delete', calendar_uid, event_uid,
                                            params=params)

        if response.status_code == 410:
            # The Google API returns an 'HTTPError: 410 Client Error: Gone'
            # for an event that no longer exists on the remote
            log.warning('Event no longer exists on remote',
                        calendar_uid=calendar_uid, event_uid=event_uid)
        else:
            # All other non-200 statuses are considered errors
            response.raise_for_status()

    # -------- logic for push notification subscriptions -------- #

    def _get_access_token_for_push_notifications(self,
                                                 account,
                                                 force_refresh=False):
        # Raises an OAuthError if no such token exists
        return g_token_manager.get_token_for_calendars_restrict_ids(
            account, PUSH_ENABLED_CLIENT_IDS, force_refresh)

    def push_notifications_enabled(self, account):
        push_enabled_creds = next(
            (creds for creds in account.valid_auth_credentials
             if creds.client_id in PUSH_ENABLED_CLIENT_IDS),
            None)
        return push_enabled_creds is not None

    def watch_calendar_list(self, account):
        """
        Subscribe to google push notifications for the calendar list.

        Returns the expiration of the notification channel (as a
        Unix timestamp in ms)

        Raises an OAuthError if no credentials are authorized to
        set up push notifications for this account.

        Raises an AccessNotEnabled error if calendar sync is not enabled
        """
        token = self._get_access_token_for_push_notifications(account)
        receiving_url = CALENDAR_LIST_WEBHOOK_URL.format(
            urllib.quote(account.public_id))
        data = {
            "id": uuid.uuid4().hex,
            "type": "web_hook",
            "address": receiving_url,
        }
        headers = {
            'content-type': 'application/json'
        }
        r = requests.post(WATCH_CALENDARS_URL,
                          data=json.dumps(data),
                          headers=headers,
                          auth=OAuthRequestsWrapper(token))

        if r.status_code == 200:
            data = r.json()
            return data.get('expiration')
        else:
            self.handle_watch_errors(r)
            return None

    def watch_calendar(self, account, calendar):
        """
        Subscribe to google push notifications for a calendar.

        Returns the expiration of the notification channel (as a
        Unix timestamp in ms)

        Raises an OAuthError if no credentials are authorized to
        set up push notifications for this account.

        Raises an AccessNotEnabled error if calendar sync is not enabled

        Raises an HTTPError if google gives us a 404 (which implies the
        calendar was deleted)
        """
        token = self._get_access_token_for_push_notifications(account)
        watch_url = WATCH_EVENTS_URL.format(urllib.quote(calendar.uid))
        receiving_url = EVENTS_LIST_WEHOOK_URL.format(
            urllib.quote(calendar.public_id))
        data = {
            "id": uuid.uuid4().hex,
            "type": "web_hook",
            "address": receiving_url,
        }
        headers = {
            'content-type': 'application/json'
        }
        try:
            r = requests.post(watch_url,
                              data=json.dumps(data),
                              headers=headers,
                              auth=OAuthRequestsWrapper(token))
        except requests.exceptions.SSLError:
            self.log.warning(
                'SSLError subscribing to Google push notifications',
                url=watch_url, exc_info=True)
            return

        if r.status_code == 200:
            data = r.json()
            return data.get('expiration')
        else:
            self.handle_watch_errors(r)
            return

    def handle_watch_errors(self, r):
        self.log.warning(
            'Error subscribing to Google push notifications', url=r.url,
            response=r.content, status=r.status_code)

        if r.status_code == 401:
            self.log.warning(
                'Invalid: could be invalid auth credentials',
                url=r.url, response=r.content, status=r.status_code)

        elif r.status_code in (500, 503):
            log.warning('Backend error in calendar API; retrying')
            gevent.sleep(30 + random.randrange(0, 60))

        elif r.status_code == 403:
            try:
                reason = r.json()['error']['errors'][0]['reason']
            except (KeyError, ValueError):
                log.error("Couldn't parse API error response",
                          response=r.content, status=r.status_code)

            if reason == 'userRateLimitExceeded':
                log.warning('API request was rate-limited; retrying')
                gevent.sleep(30 + random.randrange(0, 60))
            elif reason == 'accessNotConfigured':
                log.warning('API not enabled; returning empty result')
                raise AccessNotEnabledError()

        elif r.status_code == 404:
            # resource deleted!
            r.raise_for_status()

        else:
            self.log.warning('Unexpected error', response=r.content,
                             status=r.status_code)


def parse_calendar_response(calendar):
    """
    Constructs a Calendar object from a Google calendarList resource (a
    dictionary).  See
    http://developers.google.com/google-apps/calendar/v3/reference/calendarList

    Parameters
    ----------
    calendar: dict

    Returns
    -------
    A corresponding Calendar instance.
    """
    uid = calendar['id']
    name = calendar['summary']

    role = calendar['accessRole']
    read_only = True
    if role == "owner" or role == "writer":
        read_only = False

    description = calendar.get('description', None)
    return Calendar(uid=uid,
                    name=name,
                    read_only=read_only,
                    description=description)


def parse_event_response(event, read_only_calendar):
    """
    Constructs an Event object from a Google event resource (a dictionary).
    See https://developers.google.com/google-apps/calendar/v3/reference/events

    Parameters
    ----------
    event: dict

    Returns
    -------
    A corresponding Event instance. This instance is not committed or added to
    a session.
    """
    uid = str(event['id'])
    # The entirety of the raw event data in json representation.
    raw_data = json.dumps(event)
    title = event.get('summary', '')

    # Timing data
    _start = event['start']
    _end = event['end']
    _original = event.get('originalStartTime', {})

    event_time = google_to_event_time(_start, _end)
    original_start = parse_google_time(_original)
    start_tz = _start.get('timeZone')

    last_modified = parse_datetime(event.get('updated'))

    description = event.get('description')
    location = event.get('location')
    busy = event.get('transparency') != 'transparent'
    sequence = event.get('sequence', 0)

    # We're lucky because event statuses follow the icalendar
    # spec.
    event_status = event.get('status', 'confirmed')
    assert event_status in EVENT_STATUSES

    # Ownership, read_only information
    creator = event.get('creator')

    if creator:
        owner = u'{} <{}>'.format(
            creator.get('displayName', ''), creator.get('email', ''))
    else:
        owner = ''

    participants = []
    attendees = event.get('attendees', [])
    for attendee in attendees:
        status = STATUS_MAP[attendee.get('responseStatus')]
        participants.append({
            'email': attendee.get('email'),
            'name': attendee.get('displayName'),
            'status': status,
            'notes': attendee.get('comment')
        })

    organizer = event.get('organizer')
    is_owner = bool(organizer and organizer.get('self'))

    # FIXME @karim: The right thing here would be to use Google's ACL API.
    # There's some obscure cases, like an autoimported event which guests can
    # edit that can't be modified.
    read_only = True
    if not read_only_calendar:
        read_only = False

    # Recurring master or override info
    recurrence = event.get('recurrence')
    master_uid = event.get('recurringEventId')
    cancelled = (event.get('status') == 'cancelled')

    return Event(uid=uid,
                 raw_data=raw_data,
                 title=title,
                 description=description,
                 location=location,
                 busy=busy,
                 start=event_time.start,
                 end=event_time.end,
                 all_day=event_time.all_day,
                 owner=owner,
                 is_owner=is_owner,
                 read_only=read_only,
                 participants=participants,
                 recurrence=recurrence,
                 last_modified=last_modified,
                 original_start_tz=start_tz,
                 original_start_time=original_start,
                 master_event_uid=master_uid,
                 cancelled=cancelled,
                 status=event_status,
                 sequence_number=sequence,
                 source='local')


def _dump_event(event):
    """Convert an event db object to the Google API JSON format."""
    dump = {}
    dump["summary"] = event.title
    dump["description"] = event.description
    dump["location"] = event.location

    # Whether the event blocks time on the calendar.
    dump['transparency'] = 'opaque' if event.busy else 'transparent'

    if event.all_day:
        dump["start"] = {"date": event.start.strftime('%Y-%m-%d')}
        dump["end"] = {"date": event.start.strftime('%Y-%m-%d')}
    else:
        dump["start"] = {"dateTime": event.start.isoformat('T'),
                         "timeZone": "UTC"}
        dump["end"] = {"dateTime": event.end.isoformat('T'),
                       "timeZone": "UTC"}

    if event.participants:
        dump['attendees'] = []
        inverse_status_map = {value: key for key, value in STATUS_MAP.items()}
        for participant in event.participants:
            attendee = {}
            if 'name' in participant:
                attendee['displayName'] = participant['name']
            if 'status' in participant:
                attendee['responseStatus'] = inverse_status_map[
                    participant['status']]
            if 'email' in participant:
                attendee['email'] = participant['email']
            if 'guests' in participant:
                attendee['additionalGuests'] = participant['guests']
            if attendee:
                dump['attendees'].append(attendee)

    return dump
