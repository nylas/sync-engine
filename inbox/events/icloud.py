import json
import requests
import uuid
import hashlib
import datetime

from inbox.log import get_logger
logger = get_logger()
from inbox.basicauth import ValidationError
from inbox.models.session import session_scope
from inbox.models import Event
from inbox.sync.base_sync_provider import BaseSyncProvider
from inbox.models.backends.generic import GenericAccount
from inbox.events.util import MalformedEventError
from inbox.models.event import SUBJECT_MAX_LEN, LOCATION_MAX_LEN

ICLOUD_URL = 'https://www.icloud.com'
ICLOUD_SETUP = 'https://p12-setup.icloud.com/setup/ws/1'
ICLOUD_LOGIN = ICLOUD_SETUP + '/login'
ICLOUD_VALIDATE = ICLOUD_SETUP + '/validate'


class ICloudEventsProvider(BaseSyncProvider):
    """A utility class to fetch and parse iCloud calendar data for the
    specified account using the iCloud webservices api

    Parameters
    ----------
    account_id: GenericAccount.id
        The user account for which to fetch event data.

    Attributes
    ----------
    log: logging.Logger
        Logging handler.
    """
    PROVIDER_NAME = 'icloud'

    def __init__(self, account_id):
        self.account_id = account_id
        self.log = logger.new(account_id=account_id, component='event sync',
                              provider=self.PROVIDER_NAME)

    def _parse_event(self, event):
        try:
            uid = str(event['guid'])

            # The entirety of the raw event data in json representation.
            raw_data = str(event)

            subject = event.get('title', '')[:SUBJECT_MAX_LEN]
            body = event.get('description', None)
            location = event.get('location', None)
            if location:
                location = location[:LOCATION_MAX_LEN]
            all_day = event.get('allDay', False)
            locked = event.get('readOnly')

            # for some reason iCloud gives the date as YYYYMMDD for the first
            # entry and then the Y, M, D, H, S as later entries.
            start_date = event['startDate'][1:]
            end_date = event['endDate'][1:]

            start = datetime.datetime(*start_date)
            end = datetime.datetime(*end_date)

            recurrence = event['recurrence']

            # iCloud doesn't give us busy information
            busy = True

            # reminder format is super-funky, punt for now -cg3
            reminders = str([])

            # and for some reason iCloud isn't giving us participants
            participants = []
            time_zone = 0  # iCloud gives us times in UTC when we ask for it

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
            account = db_session.query(GenericAccount).get(self.account_id)
            email_address = account.email_address
            password = account.password

        session = requests.Session()
        session.headers = {'origin': ICLOUD_URL}

        instance = uuid.uuid4().hex.encode('utf-8')
        sha_id = hashlib.sha1(email_address.encode('utf-8') + instance)

        data = json.dumps({
            'apple_id': email_address,
            'password': password,
            'id': sha_id.hexdigest().upper(),
            'extended_login': False})

        # First login to iCloud to verify credentials
        req = session.post(ICLOUD_LOGIN, data=data)

        if not req.ok:
            raise ValidationError()

        # Next validate to get the dsInfo.dsid
        req = session.get(ICLOUD_VALIDATE)
        resp = req.json()
        dsid = resp['dsInfo']['dsid']

        calendar_url = resp['webservices']['calendar']['url']
        event_url = calendar_url + '/ca/events'

        params = {
            'dsid': dsid,
            'lang': 'en-us',
            'usertz': 'UTC',
            'startDate': '1999-12-31',
            'endDate': '2999-12-31'
        }
        resp = session.get(event_url, params=params)

        response_items = resp.json()['Event']

        events = []
        for response_event in response_items:
            try:
                events.append(self._parse_event(response_event))
            except MalformedEventError:
                self.log.warning('Malformed event',
                                 icloud_event=response_event)

        return events
