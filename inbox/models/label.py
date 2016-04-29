from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship, backref, validates
from sqlalchemy.schema import UniqueConstraint

from inbox.models.base import MailSyncBase
from inbox.models.category import Category
from inbox.models.constants import MAX_LABEL_NAME_LENGTH
from nylas.logging import get_logger
log = get_logger()


class Label(MailSyncBase):
    """ Labels from the remote account backend (Gmail). """
    # TOFIX this causes an import error due to circular dependencies
    # from inbox.models.account import Account
    # `use_alter` required here to avoid circular dependency w/Account
    account_id = Column(ForeignKey('account.id', use_alter=True,
                                   name='label_fk1',
                                   ondelete='CASCADE'), nullable=False)
    account = relationship(
        'Account',
        backref=backref(
            'labels',
            # Don't load labels if the account is deleted,
            # (the labels will be deleted by the foreign key delete casade).
            passive_deletes=True),
        load_on_pending=True)

    name = Column(String(MAX_LABEL_NAME_LENGTH),
                  nullable=False)
    canonical_name = Column(String(MAX_LABEL_NAME_LENGTH), nullable=True)

    category_id = Column(ForeignKey(Category.id, ondelete='CASCADE'))
    category = relationship(
        Category,
        backref=backref('labels',
                        cascade='all, delete-orphan'))

    @validates('name')
    def sanitize_name(self, key, name):
        name = unicode(name)
        name = name.rstrip()
        if len(name) > MAX_LABEL_NAME_LENGTH:
            log.warning("Truncating label name for account {}; original name "
                        "was '{}'".format(self.account_id, name))
            name = name[:MAX_LABEL_NAME_LENGTH]
        return name

    @classmethod
    def find_or_create(cls, session, account, name, role=None):
        q = session.query(cls).filter(cls.account_id == account.id)

        if role is not None:
            q = q.filter(cls.canonical_name == role)
        else:
            # g_label may not have unicode type (in particular for a numeric
            # label, e.g. '42'), so coerce to unicode.
            name = unicode(name)
            # Remove trailing whitespace, truncate (due to MySQL limitations).
            name = name.rstrip()
            if len(name) > MAX_LABEL_NAME_LENGTH:
                log.warning("Truncating label name for account {}; "
                            "original name was '{}'" .format(account.id, name))
                name = name[:MAX_LABEL_NAME_LENGTH]
            q = q.filter(cls.name == name)

        obj = q.first()
        if obj is None:
            obj = cls(account=account, name=name, canonical_name=role)
            obj.category = Category.find_or_create(
                session, namespace_id=account.namespace.id, name=role,
                display_name=name, type_='label')
            session.add(obj)
        return obj

    __table_args__ = \
        (UniqueConstraint('account_id', 'name', 'canonical_name'),
                      {'sqlite_autoincrement': True})
