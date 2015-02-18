from pytest import fixture
from apiclient.errors import HttpError

from inbox.events.util import MalformedEventError
from inbox.events.base import BaseEventProvider


@fixture(scope='function')
def event_sync(config, db):
    from inbox.events.remote_sync import EventSync
    return EventSync('inboxapptest@gmail.com', 'gmail', 1, 1)


@fixture(scope='function')
def events_provider(config, db):
    return EventsProviderStub()


class EventsProviderStub(BaseEventProvider):
    """Events provider stub to stand in for an actual provider.
    See ContactsProviderStub.
    """
    def __init__(self, provider_name='test_provider'):
        self._events = []
        self._next_uid = 1
        self.PROVIDER_NAME = provider_name
        BaseEventProvider.__init__(self, 1, 1)

    def supply_event(self, title, description='', when={'time': 0}, busy=True,
                     location='', read_only=False, owner="",
                     reminders='[]', recurrence="", deleted=False,
                     raw_data='', is_owner=True, participants=[]):
        from inbox.models import Event
        self._events.append(Event(namespace_id=1,
                                  calendar_id=1,
                                  uid=str(self._next_uid),
                                  source='remote',
                                  provider_name=self.PROVIDER_NAME,
                                  title=title,
                                  description=description,
                                  location=location,
                                  when=when,
                                  busy=busy,
                                  is_owner=is_owner,
                                  owner=owner,
                                  read_only=read_only,
                                  raw_data=raw_data,
                                  reminders=reminders,
                                  recurrence=recurrence,
                                  deleted=deleted,
                                  participants=[]))
        self._next_uid += 1

    def supply_bad(self):
        self._events.append(None)

    def parse_event(self, event, extra):
        if event is None:
            raise MalformedEventError()
        return event

    def fetch_items(self, *args, **kwargs):
        calendar_id = self.get_calendar_id('test')
        for e in self._events:
            yield (calendar_id, e, None)


class GoogleServiceStub(dict):

    def __init__(self, error_code):
        self['items'] = [True]
        self.error_code = error_code

    def events(self):
        return self

    def list(self, calendarId, **kwargs):
        # Throw an error to test updatedMin
        if 'updatedMin' in kwargs:
            raise HttpError('error',
                            '{ "error": {"code": %s} }' % self.error_code)
        return self

    def execute(self):
        return self
