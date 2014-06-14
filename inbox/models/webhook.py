from sqlalchemy import Column, Integer, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql.expression import true

from inbox.models.mixins import HasPublicID
from inbox.models.base import MailSyncBase
from inbox.models.namespace import Namespace


class Webhook(MailSyncBase, HasPublicID):
    """ hooks that run on new messages/events """

    namespace_id = Column(ForeignKey(Namespace.id, ondelete='CASCADE'),
                          nullable=False, index=True)
    namespace = relationship(
        'Namespace',
        primaryjoin='and_(Webhook.namespace_id==Namespace.id, '
        'Namespace.deleted_at==None)')

    lens_id = Column(ForeignKey('lens.id', ondelete='CASCADE'),
                     nullable=False, index=True)
    lens = relationship(
        'Lens',
        primaryjoin='and_(Webhook.lens_id==Lens.id, Lens.deleted_at==None)')

    callback_url = Column(Text, nullable=False)
    failure_notify_url = Column(Text)

    include_body = Column(Boolean, nullable=False)
    max_retries = Column(Integer, nullable=False, server_default='3')
    retry_interval = Column(Integer, nullable=False, server_default='60')
    active = Column(Boolean, nullable=False, server_default=true())

    min_processed_id = Column(Integer, nullable=False, server_default='0')
