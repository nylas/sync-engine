from sqlalchemy import (Column, String, Text, Boolean,
                        UniqueConstraint, ForeignKey)
from sqlalchemy.orm import relationship
from sqlalchemy import event
from inbox.sqlalchemy_ext.util import (generate_public_id,
                                       propagate_soft_delete)

from inbox.models.base import MailSyncBase

from inbox.models.mixins import HasPublicID


class Calendar(MailSyncBase, HasPublicID):
    account_id = Column(ForeignKey('account.id', ondelete='CASCADE'),
                        nullable=False)
    account = relationship(
        'Account', load_on_pending=True,
        primaryjoin='and_(Calendar.account_id == Account.id, '
                    'Account.deleted_at.is_(None))')
    name = Column(String(128), nullable=True)
    provider_name = Column(String(128), nullable=True)
    description = Column(Text, nullable=True)

    # A server-provided unique ID.
    uid = Column(String(767, collation='ascii_general_ci'), nullable=False)

    read_only = Column(Boolean, nullable=False, default=False)

    __table_args__ = (UniqueConstraint('account_id', 'provider_name',
                                       'name', name='uuid'),)

    def __init__(self, uid=None, public_id=None, **kwargs):
        if not uid and not public_id:
            self.public_id = self.uid = generate_public_id()
        elif not uid:
            self.uid = generate_public_id()
        else:
            self.uid = uid
        for key, value in kwargs.items():
            setattr(self, key, value)


@event.listens_for(Calendar, 'after_update')
def _after_calendar_update(mapper, connection, target):
    """ Hook to cascade delete the events as well."""
    propagate_soft_delete(mapper, connection, target,
                          "events", "calendar_id", "id")
