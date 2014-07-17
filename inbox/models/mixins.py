from datetime import datetime
from sqlalchemy import Column, DateTime, String
from sqlalchemy.ext.hybrid import hybrid_property, Comparator

from inbox.sqlalchemy_ext.util import Base36UID, generate_public_id
from inbox.models.constants import MAX_INDEXABLE_LENGTH
from inbox.util.addr import canonicalize_address


class HasPublicID(object):
    public_id = Column(Base36UID, nullable=False,
                       index=True, default=generate_public_id)


class AddressComparator(Comparator):
    def __eq__(self, other):
        return self.__clause_element__() == canonicalize_address(other)


class HasEmailAddress(object):
    """Provides an email_address attribute, which returns as value whatever you
    set it to, but uses a canonicalized form for comparisons. So e.g.
    >>> db_session.query(Account).filter_by(
    ...    email_address='ben.bitdiddle@gmail.com').all()
    [...]
    and
    >>> db_session.query(Account).filter_by(
    ...    email_address='ben.bitdiddle@gmail.com').all()
    [...]
    will return the same results, because the two Gmail addresses are
    equivalent."""
    _raw_address = Column(String(MAX_INDEXABLE_LENGTH),
                          nullable=True, index=True)
    _canonicalized_address = Column(String(MAX_INDEXABLE_LENGTH),
                                    nullable=True, index=True)

    @hybrid_property
    def email_address(self):
        return self._raw_address

    @email_address.comparator
    def email_address(cls):
        return AddressComparator(cls._canonicalized_address)

    @email_address.setter
    def email_address(self, value):
        self._raw_address = value
        self._canonicalized_address = canonicalize_address(value)


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
