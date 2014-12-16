from sqlalchemy import Column, Integer, String, ForeignKey, func
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.schema import UniqueConstraint

from inbox.models.base import MailSyncBase
from inbox.models.tag import Tag
from inbox.models.constants import MAX_FOLDER_NAME_LENGTH, MAX_INDEXABLE_LENGTH
from inbox.log import get_logger
log = get_logger()


class Folder(MailSyncBase):
    """ Folders and labels from the remote account backend (IMAP/Exchange). """
    # `use_alter` required here to avoid circular dependency w/Account
    account_id = Column(Integer,
                        ForeignKey('account.id', use_alter=True,
                                   name='folder_fk1',
                                   ondelete='CASCADE'), nullable=False)

    # TOFIX this causes an import error due to circular dependencies
    # from inbox.models.account import Account
    account = relationship(
        'Account', backref=backref('folders', cascade='delete'),
        foreign_keys=[account_id])

    # Explicitly set collation to be case insensitive. This is mysql's default
    # but never trust defaults! This allows us to store the original casing to
    # not confuse users when displaying it, but still only allow a single
    # folder with any specific name, canonicalized to lowercase.
    name = Column(String(MAX_FOLDER_NAME_LENGTH,
                         collation='utf8mb4_general_ci'), nullable=True)
    canonical_name = Column(String(MAX_FOLDER_NAME_LENGTH), nullable=True)

    # We use an additional identifier for certain providers,
    # for e.g. EAS uses it to store the eas_folder_id
    identifier = Column(String(MAX_FOLDER_NAME_LENGTH), nullable=True)

    __table_args__ = (UniqueConstraint('account_id', 'name',
                                       'canonical_name', 'identifier'),)

    @property
    def lowercase_name(self):
        if self.name is None:
            return None
        return self.name.lower()

    @property
    def namespace(self):
        return self.account.namespace

    @classmethod
    def create(cls, account, name, session, canonical_name=None,
               identifier=None):
        if name is not None and len(name) > MAX_FOLDER_NAME_LENGTH:
            log.warning("Truncating long folder name for account {}; "
                        "original name was '{}'" .format(account.id, name))
            name = name[:MAX_FOLDER_NAME_LENGTH]
        obj = cls(account=account, name=name,
                  canonical_name=canonical_name, identifier=identifier)
        session.add(obj)
        return obj

    @classmethod
    def find_or_create(cls, session, account, name, canonical_name=None,
                       identifier=None):
        try:
            if name is not None and len(name) > MAX_FOLDER_NAME_LENGTH:
                name = name[:MAX_FOLDER_NAME_LENGTH]
            q = session.query(cls).filter_by(account_id=account.id)
            if name is not None:
                q = q.filter(func.lower(Folder.name) == func.lower(name))
            if canonical_name is not None:
                q = q.filter_by(canonical_name=canonical_name)
            if identifier is not None:
                q = q.filter_by(identifier=identifier)
            obj = q.one()
        except NoResultFound:
            obj = cls.create(account, name, session, canonical_name,
                             identifier)
        except MultipleResultsFound:
            log.info("Duplicate folder rows for folder {} for account {}"
                     .format(name, account.id))
            raise
        return obj

    def get_associated_tag(self, db_session):
        if self.canonical_name is not None:
            try:
                return db_session.query(Tag). \
                    filter(Tag.namespace_id == self.namespace.id,
                           Tag.public_id == self.canonical_name).one()
            except NoResultFound:
                # Explicitly set the namespace_id instead of the namespace
                # attribute to avoid autoflush-induced IntegrityErrors where
                # the namespace_id is null on flush.
                tag = Tag(namespace_id=self.account.namespace.id,
                          name=self.canonical_name,
                          public_id=self.canonical_name)
                db_session.add(tag)
                return tag

        else:
            tag_name = self.name.lower()[:MAX_INDEXABLE_LENGTH]
            try:
                return db_session.query(Tag). \
                    filter(Tag.namespace_id == self.namespace.id,
                           Tag.name == tag_name).one()
            except NoResultFound:
                # Explicitly set the namespace_id instead of the namespace
                # attribute to avoid autoflush-induced IntegrityErrors where
                # the namespace_id is null on flush.
                tag = Tag(namespace_id=self.account.namespace.id,
                          name=tag_name)
                db_session.add(tag)
                return tag


class FolderItem(MailSyncBase):
    """ Mapping of threads to account backend folders.

    Used to provide a read-only copy of these backend folders/labels and,
    (potentially), to sync local datastore changes to these folders back to
    the IMAP/Exchange server.

    Note that a thread may appear in more than one folder, as may be the case
    with Gmail labels.
    """
    thread_id = Column(Integer, ForeignKey('thread.id', ondelete='CASCADE'),
                       nullable=False)
    # thread relationship is on Thread to make delete-orphan cascade work

    # Might be different from what we've synced from IMAP. (Local datastore
    # changes.)
    folder_id = Column(Integer, ForeignKey(Folder.id, ondelete='CASCADE'),
                       nullable=False)

    # We almost always need the folder name too, so eager load by default.
    folder = relationship(
        'Folder', uselist=False,
        backref=backref('threads',
                        # If associated folder is deleted, don't load child
                        # objects and let database-level cascade do its thing.
                        passive_deletes=True),
        lazy='joined')

    @property
    def account(self):
        return self.folder.account

    @property
    def namespace(self):
        return self.thread.namespace
