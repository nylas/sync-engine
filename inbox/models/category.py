from datetime import datetime

from sqlalchemy import Column, String, ForeignKey, Enum, DateTime
from sqlalchemy.orm import relationship, validates
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.orm.exc import MultipleResultsFound
from sqlalchemy.ext.hybrid import hybrid_property

from inbox.sqlalchemy_ext.util import StringWithTransform
from inbox.models.base import MailSyncBase
from inbox.models.mixins import (HasRevisions, HasPublicID,
                                 CaseInsensitiveComparator, DeletedAtMixin,
                                 UpdatedAtMixin)
from inbox.models.constants import MAX_INDEXABLE_LENGTH
from nylas.logging import get_logger
from inbox.util.misc import fs_folder_path
log = get_logger()

EPOCH = datetime.utcfromtimestamp(0)


def sanitize_name(name):
    # g_label may not have unicode type (in particular for a numeric
    # label, e.g. '42'), so coerce to unicode.
    if not isinstance(name, unicode):
        name = str(name).decode('utf-8', 'ignore')

    # Remove trailing whitespace, truncate (due to MySQL limitations).
    name = name.rstrip()
    if len(name) > MAX_INDEXABLE_LENGTH:
        name = name[:MAX_INDEXABLE_LENGTH]
    return name


class CategoryNameString(StringWithTransform):
    """
    CategoryNameString is a Column type that extends our
    sqlalchemy_ext.util.StringWithTransform to initialize it with the correct
    sanitization procedure and the correct string length and collation we use
    for category names.

    We store rstripped and truncated category names, so this class will
    ensure that all strings of this type are correctly truncated and sanitized,
    and the input of any `==` queries executed against a Column of this
    type match the values that we are actually storing in the database.
    """

    def __init__(self, *args, **kwargs):
        super(CategoryNameString, self)\
            .__init__(sanitize_name, MAX_INDEXABLE_LENGTH,
                      collation='utf8mb4_bin')


class Category(MailSyncBase, HasRevisions, HasPublicID, UpdatedAtMixin,
               DeletedAtMixin):

    @property
    def API_OBJECT_NAME(self):
        return self.type_

    # Override the default `deleted_at` column with one that is NOT NULL --
    # Category.deleted_at is needed in a UniqueConstraint.
    # Set the default Category.deleted_at = EPOCH instead.
    deleted_at = Column(DateTime, index=True, nullable=False,
                        default='1970-01-01 00:00:00')

    # Need `use_alter` here to avoid circular dependencies
    namespace_id = Column(ForeignKey('namespace.id', use_alter=True,
                                     name='category_fk1',
                                     ondelete='CASCADE'), nullable=False)
    namespace = relationship('Namespace', load_on_pending=True)

    # STOPSHIP(emfree): need to index properly for API filtering performance.
    name = Column(String(MAX_INDEXABLE_LENGTH), nullable=False, default='')
    display_name = Column(CategoryNameString(), nullable=False)

    type_ = Column(Enum('folder', 'label'), nullable=False, default='folder')

    @validates('display_name')
    def validate_display_name(self, key, display_name):
        sanitized_name = sanitize_name(display_name)
        if sanitized_name != display_name:
            log.warning("Truncating category display_name", type_=self.type_,
                        original=display_name)
        return sanitized_name

    @classmethod
    def find_or_create(cls, session, namespace_id, name, display_name, type_):
        name = name or ''

        objects = session.query(cls).filter(
            cls.namespace_id == namespace_id,
            cls.display_name == display_name).all()

        if not objects:
            obj = cls(namespace_id=namespace_id, name=name,
                      display_name=display_name, type_=type_,
                      deleted_at=EPOCH)
            session.add(obj)
        elif len(objects) == 1:
            obj = objects[0]
            if not obj.name:
                # There is an existing category with this `display_name` and no
                # `name`, so update it's `name` as needed.
                # This is needed because the first time we sync generic IMAP
                # folders, they may initially have `name` == '' but later they may
                # get a `name`. At this point, it *is* the same folder so we
                # merely want to update its `name`, not create a new one.
                obj.name = name
        else:
            log.error('Duplicate category rows for namespace_id {}, '
                      'name {}, display_name: {}'.
                      format(namespace_id, name, display_name))
            raise MultipleResultsFound(
                'Duplicate category rows for namespace_id {}, name {}, '
                'display_name: {}'.format(namespace_id, name, display_name))

        return obj

    @classmethod
    def create(cls, session, namespace_id, name, display_name, type_):
        name = name or ''
        obj = cls(namespace_id=namespace_id, name=name,
                  display_name=display_name, type_=type_, deleted_at=EPOCH)
        session.add(obj)
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

        if self.namespace.account.provider not in ['gmail', 'eas']:
            return fs_folder_path(self.display_name,
                                  separator=self.namespace.account.folder_separator,
                                  prefix=self.namespace.account.folder_prefix)

        return self.display_name

    @property
    def is_deleted(self):
        return self.deleted_at > EPOCH

    __table_args__ = (UniqueConstraint('namespace_id', 'name', 'display_name',
                                       'deleted_at'),
                      UniqueConstraint('namespace_id', 'public_id'))
