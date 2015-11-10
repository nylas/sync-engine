import itertools
from collections import defaultdict

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index
from sqlalchemy.orm import (relationship, backref, validates, object_session,
                            subqueryload)

from nylas.logging import get_logger
log = get_logger()
from inbox.models.mixins import HasPublicID, HasRevisions
from inbox.models.base import MailSyncBase
from inbox.models.namespace import Namespace
from inbox.util.misc import cleanup_subject


class Thread(MailSyncBase, HasPublicID, HasRevisions):
    """
    Threads are a first-class object in Inbox. This thread aggregates
    the relevant thread metadata from elsewhere so that clients can only
    query on threads.

    A thread can be a member of an arbitrary number of folders.

    If you're attempting to display _all_ messages a la Gmail's All Mail,
    don't query based on folder!

    """
    API_OBJECT_NAME = 'thread'

    namespace_id = Column(ForeignKey(Namespace.id, ondelete='CASCADE'),
                          nullable=False, index=True)
    namespace = relationship('Namespace',
                             backref=backref('threads', passive_deletes=True),
                             load_on_pending=True)

    subject = Column(String(255), nullable=True)
    # a column with the cleaned up version of a subject string, to speed up
    # threading queries.
    _cleaned_subject = Column(String(255), nullable=True)
    subjectdate = Column(DateTime, nullable=False, index=True)
    recentdate = Column(DateTime, nullable=False, index=True)
    snippet = Column(String(191), nullable=True, default='')
    version = Column(Integer, nullable=True, server_default='0')

    @validates('subject')
    def compute_cleaned_up_subject(self, key, value):
        self._cleaned_subject = cleanup_subject(value)
        return value

    @validates('messages')
    def update_from_message(self, k, message):
        with object_session(self).no_autoflush:
            if message.is_draft:
                # Don't change subjectdate, recentdate, or unread/unseen based
                # on drafts
                return message

            if message.received_date > self.recentdate:
                self.recentdate = message.received_date
                self.snippet = message.snippet

            # Subject is subject of original message in the thread
            if message.received_date < self.subjectdate:
                self.subject = message.subject
                self.subjectdate = message.received_date
            return message

    @property
    def receivedrecentdate(self):
        received_recent_date = None
        for m in self.messages:
            if all(category.name != "sent" for category in m.categories) and \
                    not m.is_draft and not m.is_sent:
                if not received_recent_date or \
                        m.received_date > received_recent_date:
                    received_recent_date = m.received_date

        if not received_recent_date:
            sorted_messages = sorted(self.messages,
                                     key=lambda m: m.received_date)
            if not sorted_messages:
                log.warning('Thread does not have associated messages',
                            thread_id=self.id)
                return None
            received_recent_date = sorted_messages[-1].received_date

        return received_recent_date

    @property
    def unread(self):
        return not all(m.is_read for m in self.messages if not m.is_draft)

    @property
    def starred(self):
        return any(m.is_starred for m in self.messages if not m.is_draft)

    @property
    def has_attachments(self):
        return any(m.attachments for m in self.messages if not m.is_draft)

    @property
    def versioned_relationships(self):
        return ['messages']

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

    @property
    def drafts(self):
        """
        Return all drafts on this thread that don't have later revisions.

        """
        return [m for m in self.messages if m.is_draft]

    @property
    def attachments(self):
        return any(m.attachments for m in self.messages)

    @property
    def account(self):
        return self.namespace.account

    @property
    def categories(self):
        categories = set()
        for m in self.messages:
            categories.update(m.categories)
        return categories

    @property
    def tags(self):
        # For backwards-compatibility -- remove after deprecating tags API
        resp = [
            {'name': c.display_name,
             # Preserves behavior where "canonical" tags would have their role
             # as id (e.g., "inbox"
             'id': (c.name or c.public_id)} for c in self.categories
        ]
        if self.unread:
            resp.append({'name': 'unread', 'id': 'unread'})
        if self.starred:
            resp.append({'name': 'starred', 'id': 'starred'})
        return resp

    @classmethod
    def api_loading_options(cls, expand=False):
        message_columns = ['public_id', 'is_draft', 'from_addr', 'to_addr',
                           'cc_addr', 'bcc_addr', 'is_read', 'is_starred',
                           'received_date', 'is_sent']
        if expand:
            message_columns += ['subject', 'snippet', 'version', 'from_addr',
                                'to_addr', 'cc_addr', 'bcc_addr', 'reply_to']
        return (
            subqueryload(Thread.messages).
            load_only(*message_columns)
            .joinedload('messagecategories')
            .joinedload('category'),
            subqueryload(Thread.messages)
            .joinedload('parts')
            .joinedload('block')
        )

    discriminator = Column('type', String(16))
    __mapper_args__ = {'polymorphic_on': discriminator}

# The /threads API endpoint filters on namespace_id and deleted_at, then orders
# by recentdate; add an explicit index to persuade MySQL to do this in a
# somewhat performant manner.
Index('ix_thread_namespace_id_recentdate_deleted_at',
      Thread.namespace_id, Thread.recentdate, Thread.deleted_at)
# Need to explicitly specify the index length for MySQL 5.6, because the
# subject column is too long to be fully indexed with utf8mb4 collation.
Index('ix_thread_subject', Thread.subject, mysql_length=191)
Index('ix_cleaned_subject', Thread._cleaned_subject, mysql_length=191)
