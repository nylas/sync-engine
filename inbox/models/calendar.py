from sqlalchemy import (Column, String, Text, Boolean,
                        UniqueConstraint, ForeignKey)
from sqlalchemy.orm import relationship
from inbox.sqlalchemy_ext.util import generate_public_id

from inbox.models.base import MailSyncBase
from inbox.models.namespace import Namespace

from inbox.models.mixins import HasPublicID


class Calendar(MailSyncBase, HasPublicID):
    namespace_id = Column(ForeignKey(Namespace.id, ondelete='CASCADE'),
                          nullable=False)

    namespace = relationship(Namespace, load_on_pending=True)

    name = Column(String(128), nullable=True)
    provider_name = Column(String(128), nullable=True)
    description = Column(Text, nullable=True)

    # A server-provided unique ID.
    uid = Column(String(767, collation='ascii_general_ci'), nullable=False)

    read_only = Column(Boolean, nullable=False, default=False)

    __table_args__ = (UniqueConstraint('namespace_id', 'provider_name',
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
