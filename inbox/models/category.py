from sqlalchemy import Column, String, ForeignKey, Enum
from sqlalchemy.orm import relationship, validates
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.ext.hybrid import hybrid_property

from inbox.models.base import MailSyncBase
from inbox.models.mixins import (HasRevisions, HasPublicID,
                                 CaseInsensitiveComparator)
from inbox.models.constants import MAX_INDEXABLE_LENGTH
from nylas.logging import get_logger
from inbox.util.misc import fs_folder_path, is_imap_folder_path
log = get_logger()


class Category(MailSyncBase, HasRevisions, HasPublicID):

    @property
    def API_OBJECT_NAME(self):
        return self.type_

    # Need `use_alter` here to avoid circular dependencies
    namespace_id = Column(ForeignKey('namespace.id', use_alter=True,
                                     name='category_fk1',
                                     ondelete='CASCADE'), nullable=False)
    namespace = relationship('Namespace', load_on_pending=True)

    # STOPSHIP(emfree): need to index properly for API filtering performance.
    name = Column(String(MAX_INDEXABLE_LENGTH), nullable=True)
    display_name = Column(String(MAX_INDEXABLE_LENGTH), nullable=False)

    type_ = Column(Enum('folder', 'label'), nullable=False, default='folder')

    @validates('display_name')
    def sanitize_display_name(self, key, display_name):
        if self.type_ == 'label':
            display_name = unicode(display_name)
        display_name = display_name.rstrip()
        if len(display_name) > MAX_INDEXABLE_LENGTH:
            log.warning('Truncating category name',
                        type_=self.type_, original=display_name)
            display_name = display_name[:MAX_INDEXABLE_LENGTH]
        return display_name

    @classmethod
    def find_or_create(cls, session, namespace_id, name, display_name, type_):
        try:
            obj = session.query(cls).filter(
                cls.namespace_id == namespace_id,
                cls.display_name == display_name).one()
        except NoResultFound:
            obj = cls(namespace_id=namespace_id, name=name,
                      display_name=display_name, type_=type_)
            session.add(obj)
        except MultipleResultsFound:
            log.error('Duplicate category rows for namespace_id {}, '
                      'name {}, display_name: {}'.
                      format(namespace_id, name, display_name))
            raise

        if obj.name is None:
            obj.name = name

        return obj

    @property
    def account(self):
        return self.namespace.account

    @property
    def type(self):
        return self.account.category_type

    @hybrid_property
    def lowercase_name(self):
        return self.display_name.lower()

    @lowercase_name.comparator
    def lowercase_name(cls):
        return CaseInsensitiveComparator(cls.display_name)

    @property
    def api_display_name(self):
        if self.namespace.account.provider == 'gmail':
            if self.display_name.startswith('[Gmail]/'):
                return self.display_name[8:]
            elif self.display_name.startswith('[Google Mail]/'):
                return self.display_name[14:]

        if self.namespace.account.provider in ['generic', 'fastmail'] and \
                is_imap_folder_path(self.display_name):
            return fs_folder_path(self.display_name)

        return self.display_name

    __table_args__ = (UniqueConstraint('namespace_id', 'name', 'display_name',
                                       'deleted_at'),
                      UniqueConstraint('namespace_id', 'public_id'),
                      {'sqlite_autoincrement': True})
