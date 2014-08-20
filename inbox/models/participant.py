from sqlalchemy import Column, String, Text, Enum, UniqueConstraint, ForeignKey
from sqlalchemy.ext.declarative import declared_attr

from inbox.models.base import MailSyncBase

from inbox.models.mixins import HasEmailAddress, HasPublicID


class Participant(MailSyncBase, HasEmailAddress, HasPublicID):
    event_id = Column(ForeignKey('event.id', ondelete='CASCADE'),
                      nullable=False)

    participant_cascade = "save-update, merge, delete, delete-orphan"

    __table_args__ = (UniqueConstraint('_raw_address',
                                       'event_id', name='uid'),)

    name = Column(String(255), nullable=True)
    status = Column(Enum('yes', 'no', 'maybe', 'awaiting'),
                    default='awaiting', nullable=False)
    notes = Column(Text, nullable=True)

    @declared_attr
    def __tablename__(cls):
        return 'eventparticipant'
