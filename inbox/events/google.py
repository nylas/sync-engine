"""Provide Google Calendar events."""
import collections
import datetime
import json
import urllib
import requests

from inbox.log import get_logger
from inbox.models import Event, Calendar, Account
from inbox.models.session import session_scope
from inbox.models.backends.oauth import token_manager
from inbox.events.util import parse_datetime

log = get_logger()
CALENDARS_URL = 'https://www.googleapis.com/calendar/v3/users/me/calendarList'
STATUS_MAP = {'accepted': 'yes', 'needsAction': 'noreply',
              'declined': 'no', 'tentative': 'maybe'}


# Container for a parsed API response. API calls return adds/updates/deletes
# all together, but we want to handle deletions separately in our persistence
# logic. deleted_uids should be a list of uids, and updated_objects should be a
# list of (un-added, uncommitted) model instances.
SyncResponse = collections.namedtuple('SyncResponse',
                                      ['deleted_uids', 'updated_objects'])


class GoogleEventsProvider(object):
    """
    A utility class to fetch and parse Google calendar data for the
    specified account using the Google Calendar API.
    """

    def __init__(self, account_id, namespace_id):
        self.account_id = account_id
        self.namespace_id = namespace_id
        self.log = log.new(account_id=account_id)

    def sync_calendars(self):
        """ Fetches data for the user's calendars.
        Returns
        -------
        SyncResponse
        """

        deletes = []
        updates = []
        items = self._get_raw_calendars()
        for item in items:
            if item.get('deleted'):
                deletes.append(item['id'])
            else:
                updates.append(parse_calendar_response(item))

        return SyncResponse(deletes, updates)

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
        SyncResponse
        """
        deletes = []
        updates = []
        items = self._get_raw_events(calendar_uid, sync_from_time)
        for item in items:
            if item.get('status') == 'cancelled':
                deletes.append(item['id'])
            else:
                updates.append(parse_event_response(item))
        return SyncResponse(deletes, updates)

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

    def _get_access_token(self):
        with session_scope() as db_session:
            acc = db_session.query(Account).get(self.account_id)
            # This will raise OAuthError if OAuth access was revoked. The
            # BaseSyncMonitor loop will catch this, clean up, and exit.
            return token_manager.get_token(acc)

    def _get_resource_list(self, url, **params):
        """Handles response pagination."""
        token = self._get_access_token()
        items = []
        next_page_token = None
        params['showDeleted'] = True
        while True:
            if next_page_token is not None:
                params['pageToken'] = next_page_token
            r = requests.get(url, params=params, auth=OAuth(token))
            if r.status_code == 200:
                data = r.json()
                items += data['items']
                next_page_token = data.get('nextPageToken')
                if next_page_token is None:
                    return items
            elif r.status_code == 401:
                # get a new access token and retry
                self.log.warning('HTTP 401 making Google Calendar API request;'
                                 ' refreshing token',
                                 url=r.url, response=r.content,
                                 status=r.status_code)
                token = self._get_access_token()
            # TODO(emfree): handle HTTP 403 / Calendar API not enabled here.
            else:
                self.log.error('HTTP error making Google Calendar API request',
                               url=r.url, response=r.content,
                               status=r.status_code)
                r.raise_for_status()

    def _make_event_request(self, method, calendar_uid, event_uid=None,
                            **kwargs):
        """Makes a POST/PUT/DELETE request for a particular event."""
        event_uid = event_uid or ''
        url = 'https://www.googleapis.com/calendar/v3/' \
              'calendars/{}/events/{}'.format(urllib.quote(calendar_uid),
                                              urllib.quote(event_uid))
        token = self._get_access_token()
        r = requests.request(method, url, auth=OAuth(token), **kwargs)
        r.raise_for_status()
        return r

    def create_remote_event(self, event):
        data = _dump_event(event)
        r = self._make_event_request('post', event.calendar.uid, json=data)
        return r.json()

    def update_remote_event(self, event):
        data = _dump_event(event)
        self._make_event_request('put', event.calendar.uid, event.uid,
                                 json=data)

    def delete_remote_event(self, calendar_uid, event_uid):
        self._make_event_request('delete', calendar_uid, event_uid)


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
    read_only = calendar['accessRole'] == 'reader'
    description = calendar.get('description', None)
    return Calendar(uid=uid,
                    name=name,
                    read_only=read_only,
                    description=description)


def parse_event_response(event):
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
    all_day = ('date' in _start and 'date' in _end)
    if all_day:
        start = parse_datetime(_start['date'])
        end = parse_datetime(_end['date']) - datetime.timedelta(days=1)
    else:
        start = parse_datetime(_start['dateTime'])
        end = parse_datetime(_end['dateTime'])

    description = event.get('description')
    location = event.get('location')
    busy = event.get('transparency') != 'transparent'

    # Ownership, read_only information
    creator = event.get('creator')

    if creator:
        owner = u'{} <{}>'.format(
            creator.get('displayName', ''), creator.get('email', ''))
    else:
        owner = ''

    is_owner = bool(creator and creator.get('self'))
    read_only = not (is_owner or event.get('guestsCanModify'))

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

    recurrence = None
    if 'recurrence' in event:
        recurrence = str(event['recurrence'])

    return Event(uid=uid,
                 raw_data=raw_data,
                 title=title,
                 description=description,
                 location=location,
                 busy=busy,
                 start=start,
                 end=end,
                 all_day=all_day,
                 owner=owner,
                 is_owner=is_owner,
                 read_only=read_only,
                 participants=participants,
                 recurrence=recurrence,
                 # TODO(emfree): remove after data cleanup
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


class OAuth(requests.auth.AuthBase):
    """Helper class for setting the Authorization header on HTTP requests."""
    def __init__(self, token):
        self.token = token

    def __call__(self, r):
        r.headers['Authorization'] = 'Bearer {}'.format(self.token)
        return r
