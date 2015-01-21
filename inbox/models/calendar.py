from sqlalchemy import (Column, String, Text, Boolean,
                        UniqueConstraint, ForeignKey)
from sqlalchemy.orm import relationship

from inbox.models.base import MailSyncBase
from inbox.models.namespace import Namespace

from inbox.models.mixins import HasPublicID


class Calendar(MailSyncBase, HasPublicID):
    namespace_id = Column(ForeignKey(Namespace.id, ondelete='CASCADE'),
                          nullable=False)

    namespace = relationship(Namespace, load_on_pending=True)

    name = Column(String(128), nullable=True)
    provider_name = Column(String(128), nullable=True, default='DEPRECATED')
    description = Column(Text, nullable=True)

    # A server-provided unique ID.
    uid = Column(String(767, collation='ascii_general_ci'), nullable=False)

    read_only = Column(Boolean, nullable=False, default=False)

    __table_args__ = (UniqueConstraint('namespace_id', 'provider_name',
                                       'name', 'uid', name='uuid'),)

    def update(self, calendar):
        self.uid = calendar.uid
        self.name = calendar.name
        self.read_only = calendar.read_only
        self.description = calendar.description
