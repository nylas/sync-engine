import requests

from inbox.log import get_logger
logger = get_logger()
from inbox.models.session import session_scope
from inbox.models import Event
from inbox.sync.base_sync_provider import BaseSyncProvider
from inbox.models.backends.outlook import OutlookAccount
from inbox.events.util import MalformedEventError, parse_datetime
from inbox.auth.outlook import OAUTH_USER_INFO_URL
from inbox.models.event import SUBJECT_MAX_LEN, LOCATION_MAX_LEN


class OutlookEventsProvider(BaseSyncProvider):
    """A utility class to fetch and parse Outlook calendar data for the
    specified account using the Outlook 365 REST API

    Parameters
    ----------
    account_id: OutlookAccount.id
        The user account for which to fetch event data.

    Attributes
    ----------
    log: logging.Logger
        Logging handler.
    """
    PROVIDER_NAME = 'outlook'

    def __init__(self, account_id):
        self.account_id = account_id
        self.log = logger.new(account_id=account_id, component='event sync',
                              provider=self.PROVIDER_NAME)

    def _parse_event(self, user_id, event):
        try:
            uid = str(event['id'])

            # The entirety of the raw event data in json representation.
            raw_data = str(event)

            subject = event.get('name', '')[:SUBJECT_MAX_LEN]
            body = event.get('description', None)
            location = event.get('location', None)
            if location:
                location = location[:LOCATION_MAX_LEN]
            all_day = event.get('is_all_day_event', False)
            locked = True

            start = parse_datetime(event['start_time'])
            end = parse_datetime(event['end_time'])

            # See if we made the event
            if 'from' in event['from']:
                if event['from'].get('id') == user_id:
                    locked = False

            recurrence = event['recurrence'] if event['is_recurrent'] else None

            busy = event['availability'] == 'busy'

            reminder_time = event.get('reminder_time')
            reminders = str([reminder_time] if reminder_time else [])

            participants = []
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
                     source='remote',
                     participants=participants)

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
        ..models.tables.base.Events
            The events that have been updated since the last account sync.
        """

        response_items = []
        with session_scope() as db_session:
            account = db_session.query(OutlookAccount).get(self.account_id)
            access_token = account.access_token

            params = {'access_token': access_token}

            path = OAUTH_USER_INFO_URL + "/events"
            resp = requests.get(path, params=params)

            if resp.status_code != 200:
                self.log.error("Error obtaining events",
                               provider=self.PROVIDER_NAME,
                               account_id=self.account_id)
                return response_items

            response_items = resp.json()['data']

            user_id = account.o_id

        # for duplicate detection since Outlook 365 provides repeates of events
        stored_event_uids = []
        events = []
        for response_event in response_items:
            try:
                new_event = self._parse_event(user_id, response_event)
                if new_event.uid not in stored_event_uids:
                    events.append(new_event)
                    stored_event_uids.append(new_event.uid)
            except MalformedEventError:
                self.log.warning('Malformed event',
                                 outlook_event=response_event)

        return events
