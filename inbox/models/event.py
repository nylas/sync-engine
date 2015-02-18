from datetime import datetime
time_parse = datetime.utcfromtimestamp
from dateutil.parser import parse as date_parse
from copy import deepcopy

from sqlalchemy import (Column, String, ForeignKey, Text, Boolean,
                        DateTime, Enum, UniqueConstraint, Index)
from sqlalchemy.orm import relationship, backref, validates

from inbox.util.misc import merge_attr
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
    calendar = relationship(Calendar,
                            backref=backref('events', passive_deletes=True),
                            load_on_pending=True)

    # A server-provided unique ID.
    uid = Column(String(767, collation='ascii_general_ci'), nullable=False)

    # A constant, unique identifier for the remote backend this event came
    # from. E.g., 'google', 'eas', 'inbox'
    provider_name = Column(String(64), nullable=False)

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
    source = Column('source', Enum('local', 'remote'))

    # Flag to set if the event is deleted in a remote backend.
    # (This is an unmapped attribute, i.e., it does not correspond to a
    # database column.)
    deleted = False

    __table_args__ = (UniqueConstraint('uid', 'source', 'namespace_id',
                                       'provider_name', name='uuid'),
                      Index('ix_event_ns_uid_provider_name',
                            'namespace_id', 'uid', 'provider_name'))

    participants = Column(MutableList.as_mutable(BigJSON), default=[],
                          nullable=True)

    @validates('reminders', 'recurrence', 'owner', 'location', 'title',
               'raw_data')
    def validate_length(self, key, value):
        max_len = _LENGTHS[key]
        return value if value is None else value[:max_len]

    def merge_participants(self, base, remote):
        # Merge participants. Remote always take precedence.
        self.participants = deepcopy(remote)

    def merge_from(self, base, remote):
        # This must be updated when new fields are added to the class.
        merge_attrs = ['title', 'description', 'start', 'end', 'all_day',
                       'read_only', 'location', 'reminders', 'recurrence',
                       'busy', 'raw_data', 'owner', 'is_owner', 'calendar_id']

        for attr in merge_attrs:
            merge_attr(base, remote, self, attr)

        self.merge_participants(base.participants, remote.participants)

    def copy_from(self, src):
        """ Copy fields from src."""
        self.namespace_id = src.namespace_id
        self.namespace = src.namespace
        self.uid = src.uid
        self.provider_name = src.provider_name
        self.raw_data = src.raw_data
        self.title = src.title
        self.description = src.description
        self.busy = src.busy
        self.read_only = src.read_only
        self.is_owner = src.is_owner
        self.owner = self.owner
        self.location = src.location
        self.reminders = src.reminders
        self.recurrence = src.recurrence
        self.start = src.start
        self.end = src.end
        self.all_day = src.all_day
        self.calendar_id = src.calendar_id
        self.participants = src.participants

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
