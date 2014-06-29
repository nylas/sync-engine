from sqlalchemy import Column, Integer
from sqlalchemy.ext.declarative import as_declarative, declared_attr

from inbox.models.mixins import AutoTimestampMixin

MAX_INDEXABLE_LENGTH = 191
MAX_FOLDER_NAME_LENGTH = MAX_INDEXABLE_LENGTH


@as_declarative()
class MailSyncBase(AutoTimestampMixin):
    """
    Provides automated table name, primary key column, and audit timestamps.
    """
    id = Column(Integer, primary_key=True, autoincrement=True)

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()

    @declared_attr
    def __table_args__(cls):
        return {'extend_existing': True}
