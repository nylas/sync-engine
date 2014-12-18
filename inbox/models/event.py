from datetime import datetime
time_parse = datetime.utcfromtimestamp
from dateutil.parser import parse as date_parse

from sqlalchemy import (Column, String, ForeignKey, Text, Boolean,
                        DateTime, Enum, UniqueConstraint)
from sqlalchemy.orm import relationship, backref, validates

from inbox.util.misc import merge_attr
from inbox.sqlalchemy_ext.util import MAX_TEXT_LENGTH, JSON, MutableDict
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
                                       'provider_name', name='uuid'),)

    _participant_cascade = "save-update, merge, delete, delete-orphan"
    participants_by_email = Column(MutableDict.as_mutable(JSON), default={},
                                   nullable=True)

    def __init__(self, *args, **kwargs):
        MailSyncBase.__init__(self, *args, **kwargs)
        if self.participants_by_email is None:
            self.participants_by_email = {}

    @validates('reminders', 'recurrence', 'owner', 'location', 'title', 'raw_data')
    def validate_length(self, key, value):
        max_len = _LENGTHS[key]
        return value if value is None else value[:max_len]

    @property
    def participants(self):
        return self.participants_by_email.values()

    @participants.setter
    def participants(self, participants):
        # We need to do this because the codes which creates event often
        # does it by calling something like event = Event(..., participants=[])
        # in this case self.participants_by_email is None since the constructor
        # hasn't run yet.
        if self.participants_by_email is None:
            self.participants_by_email = {}

        for p in participants:
            self.participants_by_email[p['email_address']] = p

    # Use a list for lowing to json to preserve original order
    @property
    def participant_list(self):
        return [{'name': p['name'],
                 'email': p['email_address'],
                 'status': p['status'],
                 'notes': p['notes'],
                 'id': p['public_id']}
                for p in self.participants_by_email.values()]

    @participant_list.setter
    def participant_list(self, p_list):
        """ Updates the participant list based off of a list so that order can
        be preserved from creation time. (Doesn't allow re-ordering)"""

        # First add or update the ones we don't have yet
        all_emails = []

        for p in p_list:
            all_emails.append(p['email'])
            existing = self.participants_by_email.get(p['email'])
            if existing:
                existing['name'] = p.get('name')
                existing['notes'] = p.get('notes')
                existing['status'] = p.get('status')
            else:
                new_p = {"name": p.get('name'),
                         "email_address": p['email'],
                         "notes": p.get('notes'),
                         "status": p.get('status')}
                self.participants_by_email[p['email']] = new_p

        # Now remove the ones we have stored that are not in the list
        remove = list(set(self.participants_by_email.keys()) - set(all_emails))
        for email in remove:
            del self.participants_by_email[email]

    def merge_participant(self, p_email, base, remote):
        if p_email not in self.participants_by_email:
            # Removed locally, so don't add
            if base and remote:
                return
            new_p = {"email_address": p_email}
            self.participants_by_email[p_email] = new_p
        else:
            # Removed by remote, don't add
            if base and not remote:
                del self.participants_by_email[p_email]
                return

        dest = self.participants_by_email.get(p_email)

        merge_attrs = ['name', 'status', 'notes']

        for attr in merge_attrs:
            merge_attr(base, remote, dest, attr)

    def merge_participants(self, base, remote):
        all_participants = list(set(base.keys()) |
                                set(remote.keys()) |
                                set(self.participants_by_email.keys()))

        for p_email in all_participants:
            base_value = base.get(p_email)
            remote_value = remote.get(p_email)
            self.merge_participant(p_email, base_value, remote_value)

    def merge_from(self, base, remote):
        # This must be updated when new fields are added to the class.
        merge_attrs = ['title', 'description', 'start', 'end', 'all_day',
                       'read_only', 'location', 'reminders', 'recurrence',
                       'busy', 'raw_data', 'owner', 'is_owner', 'calendar_id']

        for attr in merge_attrs:
            merge_attr(base, remote, self, attr)

        self.merge_participants(base.participants_by_email,
                                remote.participants_by_email)

    def _copy_participant(self, copy, src):
        if src['status'] is None:
            src['status'] = 'noreply'
            copy['status'] = 'noreply'

        if 'email_address' in src:
            copy['email_address'] = src['email_address']

        if 'status' in src:
            copy['status'] = src['status']

        if 'name' in src:
            copy['name'] = src['name']

        if 'notes' in src:
            copy['notes'] = src['notes']

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

        for p_email, p in src.participants_by_email.iteritems():
            if p_email not in self.participants_by_email:
                self.participants_by_email[p_email] = p
            else:
                old_p = self.participants_by_email[p_email]
                self._copy_participant(old_p, p)

        # For some reason sqlalchemy doesn't like iterating and modifying
        # a collection at the same time.
        emails = self.participants_by_email.keys()
        for p_email in emails:
            if p_email not in src.participants_by_email:
                del self.participants_by_email[p_email]

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

    @property
    def versioned_relationships(self):
        return ['participants_by_email']
