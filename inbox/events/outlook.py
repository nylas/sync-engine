import requests

from inbox.log import get_logger
logger = get_logger()
from inbox.models.session import session_scope
from inbox.models import Event
from inbox.models.backends.outlook import OutlookAccount
from inbox.events.util import MalformedEventError, parse_datetime
from inbox.auth.outlook import OAUTH_USER_INFO_URL
from inbox.models.event import TITLE_MAX_LEN, LOCATION_MAX_LEN
from inbox.events.base import BaseEventProvider


class OutlookEventsProvider(BaseEventProvider):
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

    def parse_event(self, event, extra):
        user_id = extra['user_id']
        stored_uids = extra['stored_uids']
        try:
            uid = str(event['id'])

            if uid in stored_uids:
                raise MalformedEventError()

            # The entirety of the raw event data in json representation.
            raw_data = str(event)

            title = event.get('name', '')[:TITLE_MAX_LEN]
            description = event.get('description', None)
            location = event.get('location', None)
            if location:
                location = location[:LOCATION_MAX_LEN]
            all_day = event.get('is_all_day_event', False)
            read_only = True
            is_owner = False
            owner = None

            start = parse_datetime(event['start_time'])
            end = parse_datetime(event['end_time'])

            # See if we made the event
            if 'from' in event['from']:
                if event['from'].get('id') == user_id:
                    is_owner = True
                    read_only = False
                else:
                    is_owner = False
                    owner = event['from'].get('name')

            recurrence = event['recurrence'] if event['is_recurrent'] else None

            busy = event['availability'] == 'busy'

            reminder_time = event.get('reminder_time')
            reminders = str([reminder_time] if reminder_time else [])

            participants = []

        except (KeyError, AttributeError):
            raise MalformedEventError()

        stored_uids.append(uid)

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
                     busy=busy,
                     all_day=all_day,
                     read_only=read_only,
                     is_owner=is_owner,
                     owner=owner,
                     source='remote',
                     participants=participants)

    def fetch_items(self, sync_from_time=None):
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
                return

            response_items = resp.json()['data']
            user_id = account.o_id

        calendar_id = self.get_calendar_id('default')
        extra = {'user_id': user_id, 'stored_uids': []}
        for response_event in response_items:
            yield (calendar_id, response_event, extra)
