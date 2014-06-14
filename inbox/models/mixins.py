from datetime import datetime
from sqlalchemy import Column, DateTime

from inbox.sqlalchemy_ext.util import Base36UID, generate_public_id


class HasPublicID(object):
    public_id = Column(Base36UID, nullable=False,
                       index=True, default=generate_public_id)


class AutoTimestampMixin(object):
    # We do all default/update in Python not SQL for these because MySQL
    # < 5.6 doesn't support multiple TIMESTAMP cols per table, and can't
    # do function defaults or update triggers on DATETIME rows.
    created_at = Column(DateTime, default=datetime.utcnow,
                        nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow,
                        onupdate=datetime.utcnow, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True, index=True)

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def mark_deleted(self):
        """
        Safer object deletion: mark as deleted and garbage collect later.
        """
        self.deleted_at = datetime.utcnow()

