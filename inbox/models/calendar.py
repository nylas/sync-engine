from sqlalchemy import (Column, String, Text, Boolean,
                        UniqueConstraint, ForeignKey)
from sqlalchemy.orm import relationship
from inbox.sqlalchemy_ext.util import generate_public_id

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
    notes = Column(Text, nullable=True)

    # A server-provided unique ID.
    uid = Column(String(767, collation='ascii_general_ci'), nullable=False)

    read_only = Column(Boolean, nullable=False, default=False)

    __table_args__ = (UniqueConstraint('account_id',
                                       'name', name='uuid'),)

    def __init__(self, uid=None, public_id=None, **kwargs):
        if not uid and not public_id:
            self.public_id = self.uid = generate_public_id()
        elif not uid:
            self.uid = generate_public_id()
        for key, value in kwargs.items():
            setattr(self, key, value)
