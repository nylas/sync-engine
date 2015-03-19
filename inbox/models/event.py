from datetime import datetime
time_parse = datetime.utcfromtimestamp
from dateutil.parser import parse as date_parse

from sqlalchemy import (Column, String, ForeignKey, Text, Boolean,
                        DateTime, Enum, Index)
from sqlalchemy.orm import relationship, backref, validates

from inbox.sqlalchemy_ext.util import MAX_TEXT_LENGTH, BigJSON, MutableList
from inbox.models.base import MailSyncBase
from inbox.models.mixins import HasPublicID, HasRevisions
from inbox.models.calendar import Calendar
from inbox.models.namespace import Namespace
from inbox.models.when import Time, TimeSpan, Date, DateSpan


TITLE_MAX_LEN = 1024
LOCATION_MAX_LEN = 255
RECURRENCE_MAX_LEN = 255
REMINDER_MAX_LEN = 255
OWNER_MAX_LEN = 1024
_LENGTHS = {'location': LOCATION_MAX_LEN,
            'owner': OWNER_MAX_LEN,
            'recurrence': RECURRENCE_MAX_LEN,
            'reminders': REMINDER_MAX_LEN,
            'title': TITLE_MAX_LEN,
            'raw_data': MAX_TEXT_LENGTH}


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
    recurrence = Column(String(RECURRENCE_MAX_LEN), nullable=True)
    start = Column(DateTime, nullable=False)
    end = Column(DateTime, nullable=True)
    all_day = Column(Boolean, nullable=False)
    is_owner = Column(Boolean, nullable=False, default=True)
    last_modified = Column(DateTime, nullable=True)

    __table_args__ = (Index('ix_event_ns_uid_calendar_id',
                            'namespace_id', 'uid', 'calendar_id'),)

    participants = Column(MutableList.as_mutable(BigJSON), default=[],
                          nullable=True)

    @validates('reminders', 'recurrence', 'owner', 'location', 'title',
               'raw_data')
    def validate_length(self, key, value):
        max_len = _LENGTHS[key]
        return value if value is None else value[:max_len]

    @property
    def when(self):
        if self.all_day:
            start = self.start.date()
            end = self.end.date()
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
