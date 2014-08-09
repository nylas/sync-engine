from sqlalchemy import (Column, Integer, String, ForeignKey, Text, Boolean,
                        DateTime, Enum)
from sqlalchemy.orm import relationship
from sqlalchemy.schema import UniqueConstraint

from inbox.models.transaction import HasRevisions
from inbox.models.base import MailSyncBase
from inbox.models.mixins import HasPublicID

from inbox.models.account import Account


class Event(MailSyncBase, HasRevisions, HasPublicID):
    """Data for events."""
    account_id = Column(ForeignKey(Account.id, ondelete='CASCADE'),
                        nullable=False)
    account = relationship(
        Account, load_on_pending=True,
        primaryjoin='and_(Event.account_id == Account.id, '
                    'Account.deleted_at.is_(None))')

    # A server-provided unique ID.
    uid = Column(String(64), nullable=False)

    # A constant, unique identifier for the remote backend this event came
    # from. E.g., 'google', 'eas', 'inbox'
    provider_name = Column(String(64), nullable=False)

    raw_data = Column(Text, nullable=False)

    subject = Column(String(255), nullable=True)
    body = Column(Text, nullable=True)
    location = Column(String(255), nullable=True)
    busy = Column(Boolean, nullable=False)
    locked = Column(Boolean, nullable=False)
    reminders = Column(String(255), nullable=True)
    recurrence = Column(String(255), nullable=True)
    start = Column(DateTime, nullable=False)
    end = Column(DateTime, nullable=True)
    all_day = Column(Boolean, nullable=False)
    time_zone = Column(Integer, nullable=False)
    source = Column('source', Enum('local', 'remote'))

    # Flag to set if the event is deleted in a remote backend.
    # (This is an unmapped attribute, i.e., it does not correspond to a
    # database column.)
    deleted = False

    __table_args__ = (UniqueConstraint('uid', 'source', 'account_id',
                                       'provider_name'),)

    def copy_from(self, src):
        """ Copy fields from src."""
        self.account_id = src.account_id
        self.account = src.account
        self.uid = src.uid
        self.provider_name = src.provider_name
        self.raw_data = src.raw_data
        self.subject = src.subject
        self.body = src.body
        self.busy = src.busy
        self.locked = src.locked
        self.reminders = src.reminders
        self.recurrence = src.recurrence
        self.start = src.start
        self.end = src.end
        self.all_day = src.all_day
        self.time_zone = src.time_zone

    @property
    def namespace(self):
        return self.account.namespace
