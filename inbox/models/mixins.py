import abc
from datetime import datetime
from sqlalchemy import Column, DateTime, String, inspect
from sqlalchemy.ext.hybrid import hybrid_property, Comparator

from inbox.sqlalchemy_ext.util import Base36UID, generate_public_id, ABCMixin
from inbox.models.constants import MAX_INDEXABLE_LENGTH
from inbox.util.addr import canonicalize_address


class HasRevisions(ABCMixin):
    """Mixin for tables that should be versioned in the transaction log."""
    @property
    def versioned_relationships(self):
        """May be overriden by subclasses. This should be the list of
        relationship attribute names that should trigger an update revision
        when changed. (We want to version changes to some, but not all,
        relationship attributes.)"""
        return []

    @property
    def should_suppress_transaction_creation(self):
        """May be overridden by subclasses. We don't want to version certain
        specific objects -- for example, Block instances that are just raw
        message parts and not real attachments. Use this property to suppress
        revisions of such objects. (The need for this is really an artifact of
        current deficiencies in our models. We should be able to get rid of it
        eventually.)"""
        return False

    # Must be defined by subclasses
    API_OBJECT_NAME = abc.abstractproperty()

    def has_versioned_changes(self):
        """Return True if the object has changes on column properties, or on
        any relationship attributes named in self.versioned_relationships."""
        obj_state = inspect(self)
        versioned_attribute_names = list(self.versioned_relationships)
        for mapper in obj_state.mapper.iterate_to_root():
            for attr in mapper.column_attrs:
                versioned_attribute_names.append(attr.key)

        for attr_name in versioned_attribute_names:
            if getattr(obj_state.attrs, attr_name).history.has_changes():
                return True
        return False


class HasPublicID(object):
    public_id = Column(Base36UID, nullable=False,
                       index=True, default=generate_public_id)


class AddressComparator(Comparator):
    def __eq__(self, other):
        return self.__clause_element__() == canonicalize_address(other)

    def like(self, term, escape=None):
        return self.__clause_element__().like(term, escape=escape)


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
        if value is not None:
            # Silently truncate if necessary. In practice, this may be too
            # long if somebody put a super-long email into their contacts by
            # mistake or something.
            value = value[:MAX_INDEXABLE_LENGTH]
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
    # DEPRECATED
    deleted_at = Column(DateTime, nullable=True, index=True)
