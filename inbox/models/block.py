from sqlalchemy import (Column, Integer, String, Boolean,
                        Enum, ForeignKey, event)
from sqlalchemy.orm import reconstructor, relationship, backref
from sqlalchemy.sql.expression import false

from inbox.models.roles import Blob
from inbox.models.mixins import HasPublicID
from inbox.models.transaction import HasRevisions
from inbox.models.base import MailSyncBase
from inbox.models.message import Message

from sqlalchemy.ext.associationproxy import association_proxy


# These are the top 15 most common Content-Type headers
# in my personal mail archive. --mg
COMMON_CONTENT_TYPES = ['text/plain',
                        'text/html',
                        'multipart/alternative',
                        'multipart/mixed',
                        'image/jpeg',
                        'multipart/related',
                        'application/pdf',
                        'image/png',
                        'image/gif',
                        'application/octet-stream',
                        'multipart/signed',
                        'application/msword',
                        'application/pkcs7-signature',
                        'message/rfc822',
                        'image/jpg']


class Block(Blob, MailSyncBase, HasRevisions, HasPublicID):
    """ Metadata for any file that we store """

    from inbox.models.namespace import Namespace

    # Save some space with common content types
    _content_type_common = Column(Enum(*COMMON_CONTENT_TYPES))
    _content_type_other = Column(String(255))
    filename = Column(String(255))

    # TODO: create a constructor that allows the 'content_type' keyword
    def __init__(self, *args, **kwargs):
        self.content_type = None
        self.size = 0
        MailSyncBase.__init__(self, *args, **kwargs)

    namespace_id = Column(Integer,
                          ForeignKey(Namespace.id, ondelete='CASCADE'),
                          nullable=False)
    namespace = relationship(
        'Namespace', backref=backref('blocks',
                                     primaryjoin='and_('
                                     'Block.namespace_id == Namespace.id, '
                                     'Block.deleted_at.is_(None))'),
        primaryjoin='and_(Block.namespace_id==Namespace.id, '
        'Namespace.deleted_at==None)',
        load_on_pending=True)

    @reconstructor
    def init_on_load(self):
        if self._content_type_common:
            self.content_type = self._content_type_common
        else:
            self.content_type = self._content_type_other


@event.listens_for(Block, 'before_insert', propagate=True)
def serialize_before_insert(mapper, connection, target):
    if target.content_type in COMMON_CONTENT_TYPES:
        target._content_type_common = target.content_type
        target._content_type_other = None
    else:
        target._content_type_common = None
        target._content_type_other = target.content_type


class Part(Block):
    """ Part is a section of a specific message. This includes message bodies
        as well as attachments.
    """

    id = Column(Integer, ForeignKey(Block.id, ondelete='CASCADE'),
                primary_key=True)

    messages = association_proxy('part_messages', 'message')

    walk_index = Column(Integer)
    content_disposition = Column(Enum('inline', 'attachment'))
    content_id = Column(String(255))  # For attachments

    is_inboxapp_attachment = Column(Boolean, server_default=false())

    @property
    def thread_id(self):
        if not self.message:
            return None
        return self.message.thread_id

    @property
    def is_attachment(self):
        return self.content_disposition is not None

    @property
    def is_embedded(self):
        return (self.content_disposition is not None and
                self.content_disposition.lower() == 'inline')


class MessagePartAssociation(MailSyncBase):
    """Association between messages and Parts"""
    message_id = Column(Integer, ForeignKey(Message.id, ondelete='CASCADE'),
                        primary_key=True)

    part_id = Column(Integer, ForeignKey(Part.id, ondelete='CASCADE'),
                     primary_key=True)

    message = relationship('Message',
               primaryjoin='and_(MessagePartAssociation.message_id==Message.id,'
               ' Message.deleted_at.is_(None))',
               backref=backref("message_parts", cascade="all, delete-orphan"))

    part = relationship('Part',
             primaryjoin='and_(Part.id==MessagePartAssociation.part_id, Part.deleted_at.is_(None))',
             backref=backref("part_messages", cascade="all, delete-orphan"))

    def __init__(self, obj):
        if type(obj) is Part:
            self.part = obj
        elif type(obj) is Message:
            self.message = obj
