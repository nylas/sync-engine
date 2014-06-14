from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship, backref

from inbox.models.base import MailSyncBase
from inbox.models.thread import Tag
from inbox.models.thread import Thread


class TagItem(MailSyncBase):
    """Mapping between user tags and threads."""
    thread_id = Column(Integer, ForeignKey(Thread.id), nullable=False)
    tag_id = Column(Integer, ForeignKey(Tag.id), nullable=False)
    thread = relationship(
        Thread,
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
