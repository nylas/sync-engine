from sqlalchemy import Column, String, Text, Enum, UniqueConstraint, ForeignKey
from sqlalchemy.ext.declarative import declared_attr

from inbox.models.base import MailSyncBase

from inbox.models.mixins import HasEmailAddress, HasPublicID
from inbox.log import get_logger
log = get_logger()


class Participant(MailSyncBase, HasEmailAddress, HasPublicID):
    event_id = Column(ForeignKey('event.id', ondelete='CASCADE'),
                      nullable=False)

    __table_args__ = (UniqueConstraint('_raw_address',
                                       'event_id', name='uid'),)

    name = Column(String(255), nullable=True)
    status = Column(Enum('yes', 'no', 'maybe', 'awaiting'),
                    default='awaiting', nullable=False)
    notes = Column(Text, nullable=True)

    @declared_attr
    def __tablename__(cls):
        return 'eventparticipant'

    def copy_from(self, src):
        if src.status is None:
            log.error("CopyError", src=src.id)
            assert False
        self.email_address = src.email_address
        self.status = src.status
        self.name = src.name
        self.notes = src.notes
