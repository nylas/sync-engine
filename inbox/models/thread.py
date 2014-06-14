import itertools

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import relationship, backref, validates, object_session
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from inbox.log import get_logger
log = get_logger()

from inbox.sqlalchemy_ext.util import JSON, Base36UID

from inbox.models.mixins import HasPublicID
from inbox.models.base import MailSyncBase
from inbox.models.transaction import HasRevisions
from inbox.models.namespace import Namespace

from inbox.models.folder import FolderItem
from inbox.models.tag import Tag
from inbox.models.message import Message, SpoolMessage


class Thread(MailSyncBase, HasPublicID, HasRevisions):
    """ Threads are a first-class object in Inbox. This thread aggregates
        the relevant thread metadata from elsewhere so that clients can only
        query on threads.

        A thread can be a member of an arbitrary number of folders.

        If you're attempting to display _all_ messages a la Gmail's All Mail,
        don't query based on folder!
    """
    subject = Column(Text, nullable=True)
    subjectdate = Column(DateTime, nullable=False)
    recentdate = Column(DateTime, nullable=False)

    folders = association_proxy(
        'folderitems', 'folder',
        creator=lambda folder: FolderItem(folder=folder))

    @validates('folderitems', include_removes=True)
    def also_set_tag(self, key, folderitem, is_remove):
        # Also add or remove the associated tag whenever a folder is added or
        # removed.
        with object_session(self).no_autoflush:
            folder = folderitem.folder
            tag = folder.get_associated_tag(object_session(self))
            if is_remove:
                self.remove_tag(tag)
            else:
                self.apply_tag(tag)
        return folderitem

    folderitems = relationship(
        FolderItem,
        backref=backref('thread',
                        uselist=False,
                        primaryjoin='and_('
                        'FolderItem.thread_id==Thread.id, '
                        'Thread.deleted_at==None)'),
        primaryjoin='and_(FolderItem.thread_id==Thread.id, '
        'FolderItem.deleted_at==None)',
        single_parent=True,
        collection_class=set,
        cascade='all, delete-orphan')

    tags = association_proxy(
        'tagitems', 'tag',
        creator=lambda tag: TagItem(tag=tag))

    namespace_id = Column(ForeignKey(Namespace.id, ondelete='CASCADE'),
                          nullable=False, index=True)
    namespace = relationship(
        'Namespace',
        primaryjoin='and_(Thread.namespace_id==Namespace.id, '
                    'Namespace.deleted_at==None)',
        backref=backref('threads',
                        primaryjoin='and_('
                        'Thread.namespace_id == Namespace.id, '
                        'Thread.deleted_at.is_(None))'))

    mailing_list_headers = Column(JSON, nullable=True)

    def update_from_message(self, message):
        if isinstance(message, SpoolMessage):
            return self

        if message.received_date > self.recentdate:
            self.recentdate = message.received_date
        # subject is subject of original message in the thread
        if message.received_date < self.recentdate:
            self.subject = message.subject
            self.subjectdate = message.received_date

        if len(message.mailing_list_headers) > len(self.mailing_list_headers):
            self.mailing_list_headers = message.mailing_list_headers

        unread_tag = self.namespace.tags['unread']
        if all(message.is_read for message in self.messages):
            self.remove_tag(unread_tag)
        else:
            self.apply_tag(unread_tag)
        return self

    @property
    def mailing_list_info(self):
        return self.mailing_list_headers

    def is_mailing_list_thread(self):
        for v in self.mailing_list_headers.itervalues():
            if (v is not None):
                return True
        return False

    @property
    def snippet(self):
        if len(self.messages):
            # Get the snippet from the most recent message
            return self.messages[-1].snippet
        return ""

    @property
    def participants(self):
        p = set()
        for m in self.messages:
            p.update(tuple(entry) for entry in
                     itertools.chain(m.from_addr, m.to_addr,
                                     m.cc_addr, m.bcc_addr))
        return p

    def apply_tag(self, tag, execute_action=False):
        """Add the given Tag instance to this thread. Does nothing if the tag
        is already applied. Contains extra logic for validating input and
        triggering dependent changes. Callers should use this method instead of
        directly calling Thread.tags.add(tag).

        Parameters
        ----------
        tag: Tag instance
        execute_action: bool
            True if adding the tag should trigger a syncback action.
        """
        if tag in self.tags:
            return
        # We need to directly access the tagitem object here in order to set
        # the 'action_pending' flag.
        tagitem = TagItem(thread=self, tag=tag)
        tagitem.action_pending = execute_action
        self.tagitems.add(tagitem)

        # Add or remove dependent tags.
        # TODO(emfree) this should eventually live in its own utility function.
        inbox_tag = self.namespace.tags['inbox']
        archive_tag = self.namespace.tags['archive']
        if tag == inbox_tag:
            self.tags.discard(archive_tag)
        elif tag == archive_tag:
            self.tags.discard(inbox_tag)

    def remove_tag(self, tag, execute_action=False):
        """Remove the given Tag instance from this thread. Does nothing if the
        tag isn't present. Contains extra logic for validating input and
        triggering dependent changes. Callers should use this method instead of
        directly calling Thread.tags.discard(tag).

        Parameters
        ----------
        tag: Tag instance
        execute_action: bool
            True if removing the tag should trigger a syncback action.
        """
        if tag not in self.tags:
            return
        # We need to directly access the tagitem object here in order to set
        # the 'action_pending' flag.
        tagitem = object_session(self).query(TagItem). \
            filter(TagItem.thread_id == self.id,
                   TagItem.tag_id == tag.id).one()
        tagitem.action_pending = execute_action
        self.tags.remove(tag)

        # Add or remove dependent tags.
        inbox_tag = self.namespace.tags['inbox']
        archive_tag = self.namespace.tags['archive']
        if tag == inbox_tag:
            self.tags.add(archive_tag)
        elif tag == archive_tag:
            self.tags.add(inbox_tag)

    discriminator = Column('type', String(16))
    __mapper_args__ = {'polymorphic_on': discriminator}


class DraftThread(MailSyncBase, HasPublicID):
    """
    For a reply draft message, holds references to the message it is
    created in reply to (thread_id, message_id)

    Used instead of creating a copy of the thread and appending the draft to
    the copy.
    """
    master_public_id = Column(Base36UID, nullable=False)
    thread_id = Column(Integer, ForeignKey(Thread.id), nullable=False)
    thread = relationship(
        'Thread', primaryjoin='and_('
        'DraftThread.thread_id==remote(Thread.id),'
        'remote(Thread.deleted_at)==None)',
        backref=backref(
            'draftthreads', primaryjoin='and_('
            'remote(DraftThread.thread_id)==Thread.id,'
            'remote(DraftThread.deleted_at)==None)'))
    message_id = Column(Integer, ForeignKey(Message.id),
                        nullable=False)

    @classmethod
    def create(cls, session, original):
        assert original

        # We always create a copy so don't raise, simply log.
        try:
            draftthread = session.query(cls).filter(
                DraftThread.master_public_id == original.public_id).one()
        except NoResultFound:
            log.info('NoResultFound for draft with public_id {0}'.
                     format(original.public_id))
        except MultipleResultsFound:
            log.info('MultipleResultsFound for draft with public_id {0}'.
                     format(original.public_id))

        draftthread = cls(master_public_id=original.public_id,
                          thread=original,
                          message_id=original.messages[0].id)
        return draftthread

    @classmethod
    def create_copy(cls, draftthread):
        draftthread_copy = cls(
            master_public_id=draftthread.master_public_id,
            thread=draftthread.thread,
            message_id=draftthread.message_id
        )

        return draftthread_copy


class TagItem(MailSyncBase):
    """Mapping between user tags and threads."""
    thread_id = Column(Integer, ForeignKey(Thread.id), nullable=False)
    tag_id = Column(Integer, ForeignKey(Tag.id), nullable=False)
    thread = relationship(
        'Thread',
        backref=backref('tagitems',
                        collection_class=set,
                        cascade='all, delete-orphan',
                        primaryjoin='and_(TagItem.thread_id==Thread.id, '
                                    'TagItem.deleted_at.is_(None))',
                        info={'versioned_properties': ['tag_id',
                                                       'action_pending']}),
        primaryjoin='and_(TagItem.thread_id==Thread.id, '
        'Thread.deleted_at.is_(None))')
    tag = relationship(
        Tag,
        backref=backref('tagitems',
                        primaryjoin='and_('
                        'TagItem.tag_id  == Tag.id, '
                        'TagItem.deleted_at.is_(None))',
                        cascade='all, delete-orphan'),
        primaryjoin='and_(TagItem.tag_id==Tag.id, '
        'Tag.deleted_at.is_(None))')

    # This flag should be set by calling code that adds or removes a tag from a
    # thread, and wants a syncback action to be associated with it as a result.
    @property
    def action_pending(self):
        if not hasattr(self, '_action_pending'):
            self._action_pending = False
        return self._action_pending

    @action_pending.setter
    def action_pending(self, value):
        self._action_pending = value

    @property
    def namespace(self):
        return self.thread.namespace
