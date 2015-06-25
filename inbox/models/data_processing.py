from sqlalchemy import Column, ForeignKey
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.dialects.mysql import MEDIUMBLOB
from sqlalchemy import DateTime

from inbox.models.base import MailSyncBase
from inbox.models.namespace import Namespace

import datetime
import json
import zlib


class DataProcessingCache(MailSyncBase):
    """Cached data used in data processing
    """
    namespace_id = Column(ForeignKey(Namespace.id, ondelete='CASCADE'),
                          nullable=False)
    _contact_rankings = Column('contact_rankings', MEDIUMBLOB)
    _contact_groups = Column('contact_groups', MEDIUMBLOB)
    contact_rankings_last_updated = Column(DateTime)
    contact_groups_last_updated = Column(DateTime)

    @property
    def contact_rankings(self):
        if self._contact_rankings is None:
            return None
        else:
            return json.loads(zlib.decompress(self._contact_rankings))

    @contact_rankings.setter
    def contact_rankings(self, value):
        self._contact_rankings = \
            zlib.compress(json.dumps(value).encode('utf-8'))
        self.contact_rankings_last_updated = datetime.datetime.now()

    @property
    def contact_groups(self):
        if self._contact_groups is None:
            return None
        else:
            return json.loads(zlib.decompress(self._contact_groups))

    @contact_groups.setter
    def contact_groups(self, value):
        self._contact_groups = zlib.compress(json.dumps(value).encode('utf-8'))
        self.contact_groups_last_updated = datetime.datetime.now()

    __table_args__ = (UniqueConstraint('namespace_id'),)
