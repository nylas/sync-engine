import arrow
from datetime import datetime
time_parse = datetime.utcfromtimestamp
from dateutil.parser import parse as date_parse
import ast

from sqlalchemy import (Column, String, ForeignKey, Text, Boolean, Integer,
                        DateTime, Enum, Index, event)
from sqlalchemy.orm import relationship, backref, validates
from sqlalchemy.types import TypeDecorator
from sqlalchemy.ext.associationproxy import association_proxy

from inbox.sqlalchemy_ext.util import MAX_TEXT_LENGTH, BigJSON, MutableList
from inbox.models.base import MailSyncBase
from inbox.models.mixins import HasPublicID, HasRevisions
from inbox.models.calendar import Calendar
from inbox.models.namespace import Namespace
from inbox.models.when import Time, TimeSpan, Date, DateSpan
from inbox.events.util import parse_rrule_datetime

from inbox.log import get_logger
log = get_logger()

TITLE_MAX_LEN = 1024
LOCATION_MAX_LEN = 255
RECURRENCE_MAX_LEN = 255
REMINDER_MAX_LEN = 255
OWNER_MAX_LEN = 1024
_LENGTHS = {'location': LOCATION_MAX_LEN,
            'owner': OWNER_MAX_LEN,
            'recurrence': MAX_TEXT_LENGTH,
            'reminders': REMINDER_MAX_LEN,
            'title': TITLE_MAX_LEN,
            'raw_data': MAX_TEXT_LENGTH}


class FlexibleDateTime(TypeDecorator):
    """Coerce arrow times to naive datetimes before handing to the database."""

    impl = DateTime

    def process_bind_param(self, value, dialect):
        if isinstance(value, arrow.arrow.Arrow):
            value = value.to('utc').naive
        if isinstance(value, datetime):
            value = arrow.get(value).to('utc').naive
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            return arrow.get(value).to('utc')

    def compare_values(self, x, y):
        if isinstance(x, datetime) or isinstance(x, int):
            x = arrow.get(x)
        if isinstance(y, datetime) or isinstance(x, int):
            y = arrow.get(y)

        return x == y


class Event(MailSyncBase, HasRevisions, HasPublicID):
    """Data for events."""
    API_OBJECT_NAME = 'event'

    # Don't surface 'remote' events in the transaction log since
    # they're an implementation detail we don't want our customers
    # to worry about.
    @property
    def should_suppress_transaction_creation(self):
        return self.source == 'remote'

    namespace_id = Column(ForeignKey(Namespace.id, ondelete='CASCADE'),
                          nullable=False)

    namespace = relationship(Namespace, load_on_pending=True)

    calendar_id = Column(ForeignKey(Calendar.id, ondelete='CASCADE'),
                         nullable=False)
    # Note that we configure a delete cascade, rather than
    # passive_deletes=True, in order to ensure that delete revisions are
    # created for events if their parent calendar is deleted.
    calendar = relationship(Calendar,
                            backref=backref('events', cascade='delete'),
                            load_on_pending=True)

    # A server-provided unique ID.
    uid = Column(String(767, collation='ascii_general_ci'), nullable=False)

    # DEPRECATED
    # TODO(emfree): remove
    provider_name = Column(String(64), nullable=False, default='DEPRECATED')
    source = Column('source', Enum('local', 'remote'), default='local')

    raw_data = Column(Text, nullable=False)

    title = Column(String(TITLE_MAX_LEN), nullable=True)
    owner = Column(String(OWNER_MAX_LEN), nullable=True)
    description = Column(Text, nullable=True)
    location = Column(String(LOCATION_MAX_LEN), nullable=True)
    busy = Column(Boolean, nullable=False, default=True)
    read_only = Column(Boolean, nullable=False)
    reminders = Column(String(REMINDER_MAX_LEN), nullable=True)
    recurrence = Column(Text, nullable=True)
    start = Column(FlexibleDateTime, nullable=False)
    end = Column(FlexibleDateTime, nullable=True)
    all_day = Column(Boolean, nullable=False)
    is_owner = Column(Boolean, nullable=False, default=True)
    last_modified = Column(FlexibleDateTime, nullable=True)

    __table_args__ = (Index('ix_event_ns_uid_calendar_id',
                            'namespace_id', 'uid', 'calendar_id'),)

    participants = Column(MutableList.as_mutable(BigJSON), default=[],
                          nullable=True)

    discriminator = Column('type', String(30))
    __mapper_args__ = {'polymorphic_on': discriminator,
                       'polymorphic_identity': 'event'}

    @validates('reminders', 'recurrence', 'owner', 'location', 'title',
               'raw_data')
    def validate_length(self, key, value):
        max_len = _LENGTHS[key]
        return value if value is None else value[:max_len]

    @property
    def when(self):
        if self.all_day:
            # Dates are stored as DateTimes so transform to dates here.
            start = arrow.get(self.start).to('utc').date()
            end = arrow.get(self.end).to('utc').date()
            return Date(start) if start == end else DateSpan(start, end)
        else:
            start = self.start
            end = self.end
            return Time(start) if start == end else TimeSpan(start, end)

    @when.setter
    def when(self, when):
        if 'time' in when:
            self.start = self.end = time_parse(when['time'])
            self.all_day = False
        elif 'start_time' in when:
            self.start = time_parse(when['start_time'])
            self.end = time_parse(when['end_time'])
            self.all_day = False
        elif 'date' in when:
            self.start = self.end = date_parse(when['date'])
            self.all_day = True
        elif 'start_date' in when:
            self.start = date_parse(when['start_date'])
            self.end = date_parse(when['end_date'])
            self.all_day = True

    def update(self, event):
        self.uid = event.uid
        self.raw_data = event.raw_data
        self.title = event.title
        self.description = event.description
        self.location = event.location
        self.start = event.start
        self.end = event.end
        self.all_day = event.all_day
        self.owner = event.owner
        self.is_owner = event.is_owner
        self.read_only = event.read_only
        self.participants = event.participants
        self.busy = event.busy
        self.reminders = event.reminders
        self.recurrence = event.recurrence
        self.last_modified = event.last_modified

    @property
    def recurring(self):
        if self.recurrence and self.recurrence != '':
            try:
                r = ast.literal_eval(self.recurrence)
                if isinstance(r, str):
                    r = [r]
                return r
            except ValueError:
                log.warn('Invalid RRULE entry for event', event_id=self.id)
                return []
        return []

    @property
    def is_recurring(self):
        return self.recurrence is not None

    @property
    def length(self):
        return self.when.delta

    @classmethod
    def __new__(cls, *args, **kwargs):
        # Decide whether or not to instantiate a RecurringEvent/Override
        # based on the kwargs we get.
        cls_ = cls
        recurrence = kwargs.get('recurrence')
        master_event_uid = kwargs.get('master_event_uid')
        if recurrence and master_event_uid:
            raise ValueError("Event can't have both recurrence and master UID")
        if recurrence and recurrence != '':
            cls_ = RecurringEvent
        if master_event_uid:
            cls_ = RecurringEventOverride
        return object.__new__(cls_, *args, **kwargs)

    def __init__(self, **kwargs):
        # Allow arguments for all subclasses to be passed to main constructor
        for k in kwargs.keys():
            if not hasattr(type(self), k):
                del kwargs[k]
        super(Event, self).__init__(**kwargs)


class RecurringEvent(Event, HasRevisions):
    """ Represents an individual one-off instance of a recurring event,
        including cancelled events.
    """
    __mapper_args__ = {'polymorphic_identity': 'recurringevent'}
    __table_args__ = None

    id = Column(Integer, ForeignKey('event.id', ondelete='CASCADE'),
                primary_key=True)
    rrule = Column(String(RECURRENCE_MAX_LEN))
    exdate = Column(Text)  # There can be a lot of exception dates
    until = Column(FlexibleDateTime, nullable=True)
    start_timezone = Column(String(35))

    override_uids = association_proxy('overrides', 'uid')

    def __init__(self, **kwargs):
        self.start_timezone = kwargs.pop('original_start_tz', None)
        kwargs['recurrence'] = repr(kwargs['recurrence'])
        super(RecurringEvent, self).__init__(**kwargs)
        try:
            self.unwrap_rrule()
        except Exception as e:
            log.error("Error parsing RRULE entry", event_id=self.id,
                      error=e, exc_info=True)

    def inflate(self, start=None, end=None):
        # Convert a RecurringEvent into a series of InflatedEvents
        # by expanding its RRULE into a series of start times.
        from inbox.events.recurring import get_start_times
        occurrences = get_start_times(self, start, end)
        return [InflatedEvent(self, o) for o in occurrences]

    def unwrap_rrule(self):
        # Unwraps the RRULE list of strings into RecurringEvent properties.
        for item in self.recurring:
            if item.startswith('RRULE'):
                self.rrule = item
                if 'UNTIL' in item:
                    for p in item.split(';'):
                        if p.startswith('UNTIL'):
                            self.until = parse_rrule_datetime(p[6:])
            elif item.startswith('EXDATE'):
                self.exdate = item

    def all_events(self, start=None, end=None):
        # Returns all inflated events along with overrides that match the
        # provided time range.
        overrides = self.overrides
        if start:
            overrides = overrides.filter(RecurringEventOverride.start > start)
        if end:
            overrides = overrides.filter(RecurringEventOverride.end < end)
        events = list(overrides)
        uids = [e.uid for e in events]
        # Remove cancellations from the override set
        events = filter(lambda e: not e.cancelled, events)
        # If an override has not changed the start time for an event, including
        # if the override is a cancellation, the RRULE doesn't include an
        # exception for it. Filter out unnecessary inflated events
        # to cover this case: they will have the same UID.
        for e in self.inflate(start, end):
            if e.uid not in uids:
                events.append(e)
        return sorted(events, key=lambda e: e.start)

    def update(self, event):
        super(RecurringEvent, self).update(event)
        if isinstance(event, type(self)):
            self.rrule = event.rrule
            self.exdate = event.exdate
            self.until = event.until
            self.start_timezone = event.start_timezone


class RecurringEventOverride(Event, HasRevisions):
    """ Represents an individual one-off instance of a recurring event,
        including cancelled events.
    """
    id = Column(Integer, ForeignKey('event.id', ondelete='CASCADE'),
                primary_key=True)
    __mapper_args__ = {'polymorphic_identity': 'recurringeventoverride',
                       'inherit_condition': (id == Event.id)}
    __table_args__ = None

    master_event_id = Column(ForeignKey('event.id'))
    master_event_uid = Column(String(767, collation='ascii_general_ci'),
                              index=True)
    original_start_time = Column(FlexibleDateTime)
    # We have to store individual cancellations as overrides, as the EXDATE
    # isn't always updated. (Fun, right?)
    cancelled = Column(Boolean, default=False)

    master = relationship(RecurringEvent, foreign_keys=[master_event_id],
                          backref=backref('overrides', lazy="dynamic"))

    def update(self, event):
        super(RecurringEventOverride, self).update(event)
        if isinstance(event, type(self)):
            self.master_event_uid = event.master_event_uid
            self.original_start_time = event.original_start_time
        self.recurrence = None  # These single instances don't recur


class InflatedEvent(Event):
    """ This represents an individual instance of a recurring event, generated
        on the fly when a recurring event is expanded.
        These are transient objects that should never be committed to the
        database.
    """
    __mapper_args__ = {'polymorphic_identity': 'inflatedevent'}
    __tablename__ = 'event'
    __table_args__ = {'extend_existing': True}

    def __init__(self, event, instance_start):
        self.master = event
        self.update(self.master)
        self.read_only = True  # Until we support modifying inflated events
        # Give inflated events a UID consisting of the master UID and the
        # original UTC start time of the inflation.
        ts_id = instance_start.strftime("%Y%m%dT%H%M%SZ")
        self.uid = "{}_{}".format(self.master.uid, ts_id)
        self.public_id = "{}_{}".format(self.master.public_id, ts_id)
        self.set_start_end(instance_start)

    def set_start_end(self, start):
        # get the length from the master event
        length = self.master.length
        self.start = start.to('utc')
        self.end = self.start + length

    def update(self, master):
        super(InflatedEvent, self).update(master)
        self.namespace_id = master.namespace_id
        self.calendar_id = master.calendar_id


def insert_warning(mapper, connection, target):
    log.warn("InflatedEvent {} shouldn't be committed".format(target))
    raise Exception("InflatedEvent should not be committed")

event.listen(InflatedEvent, 'before_insert', insert_warning)
