from sqlalchemy import Column, String, ForeignKey, DateTime, bindparam
from sqlalchemy.orm import relationship, backref, validates
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from inbox.models.base import MailSyncBase
from inbox.models.category import Category, CategoryNameString, sanitize_name
from inbox.models.mixins import UpdatedAtMixin, DeletedAtMixin
from inbox.models.constants import MAX_INDEXABLE_LENGTH
from inbox.sqlalchemy_ext.util import bakery
from nylas.logging import get_logger
log = get_logger()


class Folder(MailSyncBase, UpdatedAtMixin, DeletedAtMixin):
    """ Folders from the remote account backend (Generic IMAP/ Gmail). """
    # TOFIX this causes an import error due to circular dependencies
    # from inbox.models.account import Account
    # `use_alter` required here to avoid circular dependency w/Account
    account_id = Column(ForeignKey('account.id', use_alter=True,
                                   name='folder_fk1',
                                   ondelete='CASCADE'), nullable=False)
    account = relationship(
        'Account',
        backref=backref(
            'folders',
            # Don't load folders if the account is deleted,
            # (the folders will be deleted by the foreign key delete casade).
            passive_deletes=True),
        foreign_keys=[account_id],
        load_on_pending=True)

    # Set the name column to be case sensitive, which isn't the default for
    # MySQL. This is a requirement since IMAP allows users to create both a
    # 'Test' and a 'test' (or a 'tEST' for what we care) folders.
    # NOTE: this doesn't hold for EAS, which is case insensitive for non-Inbox
    # folders as per
    # https://msdn.microsoft.com/en-us/library/ee624913(v=exchg.80).aspx
    name = Column(CategoryNameString(), nullable=False)
    _canonical_name = Column(String(MAX_INDEXABLE_LENGTH), nullable=False,
                             default='', name="canonical_name")

    @property
    def canonical_name(self):
        return self._canonical_name

    @canonical_name.setter
    def canonical_name(self, value):
        value = value or ''
        self._canonical_name = value
        if self.category:
            self.category.name = value

    category_id = Column(ForeignKey(Category.id, ondelete='CASCADE'))
    category = relationship(
        Category,
        backref=backref('folders',
                        cascade='all, delete-orphan'))

    initial_sync_start = Column(DateTime, nullable=True)
    initial_sync_end = Column(DateTime, nullable=True)

    @validates('name')
    def validate_name(self, key, name):
        sanitized_name = sanitize_name(name)
        if sanitized_name != name:
            log.warning("Truncating folder name for account",
                        account_id=self.account_id, name=name)
        return sanitized_name

    @classmethod
    def find_or_create(cls, session, account, name, role=None):
        q = session.query(cls).filter(cls.account_id == account.id)\
            .filter(cls.name == name)

        role = role or ''
        try:
            obj = q.one()
        except NoResultFound:
            obj = cls(account=account, name=name, canonical_name=role)
            obj.category = Category.find_or_create(
                session, namespace_id=account.namespace.id, name=role,
                display_name=name, type_='folder')
            session.add(obj)
        except MultipleResultsFound:
            log.info('Duplicate folder rows for name {}, account_id {}'
                     .format(name, account.id))
            raise

        return obj

    @classmethod
    def get(cls, id_, session):
        q = bakery(lambda session: session.query(cls))
        q += lambda q: q.filter(cls.id == bindparam('id_'))
        return q(session).params(id_=id_).first()

    __table_args__ = \
        (UniqueConstraint('account_id', 'name', 'canonical_name'),)
