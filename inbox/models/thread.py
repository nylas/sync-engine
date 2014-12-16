import itertools
from collections import defaultdict

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import relationship, backref, validates, object_session

from inbox.log import get_logger
log = get_logger()

from inbox.models.mixins import HasPublicID, HasRevisions
from inbox.models.base import MailSyncBase
from inbox.models.namespace import Namespace

from inbox.models.action_log import schedule_action_for_tag
from inbox.models.folder import FolderItem
from inbox.models.tag import Tag


class Thread(MailSyncBase, HasPublicID, HasRevisions):
    """ Threads are a first-class object in Inbox. This thread aggregates
        the relevant thread metadata from elsewhere so that clients can only
        query on threads.

        A thread can be a member of an arbitrary number of folders.

        If you're attempting to display _all_ messages a la Gmail's All Mail,
        don't query based on folder!
    """
    API_OBJECT_NAME = 'thread'
    subject = Column(String(255), nullable=True, index=True)
    subjectdate = Column(DateTime, nullable=False, index=True)
    recentdate = Column(DateTime, nullable=False, index=True)
    snippet = Column(String(191), nullable=True, default='')

    folders = association_proxy(
        'folderitems', 'folder',
        creator=lambda folder: FolderItem(folder=folder))

    @validates('messages')
    def update_from_message(self, k, message):
        if message.attachments:
            attachment_tag = self.namespace.tags['attachment']
            self.apply_tag(attachment_tag)

        if message.is_draft:
            # Don't change subjectdate, recentdate, or unread/unseen based on
            # drafts
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
        backref=backref('thread', uselist=False),
        single_parent=True,
        collection_class=set,
        cascade='all, delete-orphan')

    tags = association_proxy(
        'tagitems', 'tag',
        creator=lambda tag: TagItem(tag=tag))

    @property
    def versioned_relationships(self):
        return ['tagitems', 'messages']

    namespace_id = Column(ForeignKey(Namespace.id, ondelete='CASCADE'),
                          nullable=False, index=True)
    namespace = relationship(
        'Namespace',
        backref=backref('threads'),
        load_on_pending=True)

    @property
    def participants(self):
        """
        Different messages in the thread may reference the same email
        address with different phrases. We partially deduplicate: if the same
        email address occurs with both empty and nonempty phrase, we don't
        separately return the (empty phrase, address) pair.

        """
        deduped_participants = defaultdict(set)
        for m in self.messages:
            if m.is_draft:
                # Don't use drafts to compute participants.
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
        spam_tag = self.namespace.tags['spam']
        trash_tag = self.namespace.tags['trash']
        if tag == inbox_tag:
            self.tags.discard(archive_tag)
        elif tag == archive_tag:
            self.tags.discard(inbox_tag)
        elif tag == sent_tag:
            self.tags.discard(drafts_tag)
        elif tag == spam_tag:
            self.tags.discard(inbox_tag)
        elif tag == trash_tag:
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
        self.tags.remove(tag)

        if execute_action:
            schedule_action_for_tag(tag.public_id, self, object_session(self),
                                    tag_added=False)

        # Add or remove dependent tags.
        inbox_tag = self.namespace.tags['inbox']
        archive_tag = self.namespace.tags['archive']
        unread_tag = self.namespace.tags['unread']
        unseen_tag = self.namespace.tags['unseen']
        spam_tag = self.namespace.tags['spam']
        trash_tag = self.namespace.tags['trash']
        if tag == unread_tag:
            # Remove the 'unseen' tag when the unread tag is removed.
            self.tags.discard(unseen_tag)
        if tag == inbox_tag:
            self.tags.add(archive_tag)
        elif tag == archive_tag:
            self.tags.add(inbox_tag)
        elif tag == trash_tag:
            self.tags.add(inbox_tag)
        elif tag == spam_tag:
            self.tags.add(inbox_tag)

    @property
    def drafts(self):
        """
        Return all drafts on this thread that don't have later revisions.

        """
        return [m for m in self.messages if m.is_draft]

    discriminator = Column('type', String(16))
    __mapper_args__ = {'polymorphic_on': discriminator}


# The /threads API endpoint filters on namespace_id and deleted_at, then orders
# by recentdate; add an explicit index to persuade MySQL to do this in a
# somewhat performant manner.
Index('ix_thread_namespace_id_recentdate_deleted_at',
      Thread.namespace_id, Thread.recentdate, Thread.deleted_at)


class TagItem(MailSyncBase):
    """Mapping between user tags and threads."""
    thread_id = Column(Integer, ForeignKey(Thread.id,
                                           ondelete='CASCADE'), nullable=False)
    tag_id = Column(Integer, ForeignKey(Tag.id,
                                        ondelete='CASCADE'), nullable=False)
    thread = relationship(
        'Thread',
        backref=backref('tagitems',
                        collection_class=set,
                        cascade='all, delete-orphan'))
    tag = relationship(
        Tag,
        backref=backref('tagitems',
                        cascade='all, delete-orphan'))

    @property
    def namespace(self):
        return self.thread.namespace
