import itertools
from collections import defaultdict

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import relationship, backref, validates, object_session

from inbox.log import get_logger
log = get_logger()

from inbox.models.mixins import HasPublicID
from inbox.models.base import MailSyncBase
from inbox.models.transaction import HasRevisions
from inbox.models.namespace import Namespace

from inbox.models.action_log import schedule_action_for_tag
from inbox.models.folder import FolderItem
from inbox.models.tag import Tag
from inbox.models.message import SpoolMessage


class Thread(MailSyncBase, HasPublicID, HasRevisions):
    """ Threads are a first-class object in Inbox. This thread aggregates
        the relevant thread metadata from elsewhere so that clients can only
        query on threads.

        A thread can be a member of an arbitrary number of folders.

        If you're attempting to display _all_ messages a la Gmail's All Mail,
        don't query based on folder!
    """
    subject = Column(String(255), nullable=True)
    subjectdate = Column(DateTime, nullable=False)
    recentdate = Column(DateTime, nullable=False)
    snippet = Column(String(191), nullable=True, default='')

    folders = association_proxy(
        'folderitems', 'folder',
        creator=lambda folder: FolderItem(folder=folder))

    @validates('messages')
    def update_from_message(self, k, message):
        if isinstance(message, SpoolMessage):
            return message

        if message.received_date > self.recentdate:
            self.recentdate = message.received_date
            # Only update the thread's unread/unseen properties if this is the
            # most recent message we have synced in the thread.
            # This is so that if a user has already marked the thread as read
            # or seen via the API, but we later sync older messages in the
            # thread, it doesn't become re-unseen.
            unread_tag = self.namespace.tags['unread']
            unseen_tag = self.namespace.tags['unseen']
            if message.is_read:
                self.remove_tag(unread_tag)
            else:
                self.apply_tag(unread_tag)
                self.apply_tag(unseen_tag)
            self.snippet = message.snippet

        # subject is subject of original message in the thread
        if message.received_date < self.subjectdate:
            self.subject = message.subject
            self.subjectdate = message.received_date

        return message

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
                        'Thread.deleted_at.is_(None))'),
        load_on_pending=True)

    @property
    def participants(self):
        """Different messages in the thread may reference the same email
        address with different phrases. We partially deduplicate: if the same
        email address occurs with both empty and nonempty phrase, we don't
        separately return the (empty phrase, address) pair.
        """
        deduped_participants = defaultdict(set)
        for m in self.messages:
            if m.is_draft:
                if isinstance(m, SpoolMessage) and not m.is_latest:
                    # Don't use old draft revisions to compute participants.
                    continue
            for phrase, address in itertools.chain(m.from_addr, m.to_addr,
                                                   m.cc_addr, m.bcc_addr):
                    deduped_participants[address].add(phrase.strip())
        p = []
        for address, phrases in deduped_participants.iteritems():
            for phrase in phrases:
                if phrase != '' or len(phrases) == 1:
                    p.append((phrase, address))
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
        self.tags.add(tag)

        if execute_action:
            schedule_action_for_tag(tag.public_id, self, object_session(self),
                                    tag_added=True)

        # Add or remove dependent tags.
        # TODO(emfree) this should eventually live in its own utility function.
        inbox_tag = self.namespace.tags['inbox']
        archive_tag = self.namespace.tags['archive']
        sent_tag = self.namespace.tags['sent']
        drafts_tag = self.namespace.tags['drafts']
        if tag == inbox_tag:
            self.tags.discard(archive_tag)
        elif tag == archive_tag:
            self.tags.discard(inbox_tag)
        elif tag == sent_tag:
            self.tags.discard(drafts_tag)

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
        self.tags.remove(tag)

        if execute_action:
            schedule_action_for_tag(tag.public_id, self, object_session(self),
                                    tag_added=False)

        # Add or remove dependent tags.
        inbox_tag = self.namespace.tags['inbox']
        archive_tag = self.namespace.tags['archive']
        unread_tag = self.namespace.tags['unread']
        unseen_tag = self.namespace.tags['unseen']
        if tag == unread_tag:
            # Remove the 'unseen' tag when the unread tag is removed.
            self.tags.discard(unseen_tag)
        if tag == inbox_tag:
            self.tags.add(archive_tag)
        elif tag == archive_tag:
            self.tags.add(inbox_tag)

    @property
    def latest_drafts(self):
        """Return all drafts on this thread that don't have later revisions.
        """
        drafts = []
        # TODO(emfree) we can probably clean this up after
        # https://review.inboxapp.com/T163 is fixed.
        for message in self.messages:
            if not message.is_draft:
                continue
            if isinstance(message, SpoolMessage):
                if message.is_latest:
                    drafts.append(message)
            else:
                # This message object is a draft that was synced from backend,
                # so is not a SpoolMessage instance.
                drafts.append(message)
        return drafts

    discriminator = Column('type', String(16))
    __mapper_args__ = {'polymorphic_on': discriminator}


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
                        info={'versioned_properties': ['tag_id']}),
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

    @property
    def namespace(self):
        return self.thread.namespace
