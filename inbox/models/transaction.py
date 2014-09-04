from sqlalchemy import Column, Integer, String, ForeignKey, Index
from sqlalchemy.orm import relationship

from inbox.log import get_logger
log = get_logger()

from inbox.sqlalchemy_ext.util import BigJSON
from inbox.sqlalchemy_ext.revision import Revision, gen_rev_role

from inbox.models.base import MailSyncBase
from inbox.models.mixins import HasPublicID
from inbox.models.namespace import Namespace


class Transaction(MailSyncBase, Revision, HasPublicID):

    """ Transactional log to enable client syncing. """
    # Do delete transactions if their associated namespace is deleted.
    namespace_id = Column(Integer,
                          ForeignKey(Namespace.id, ondelete='CASCADE'),
                          nullable=False)
    namespace = relationship(
        Namespace,
        primaryjoin='and_(Transaction.namespace_id == Namespace.id, '
                    'Namespace.deleted_at.is_(None))')

    object_public_id = Column(String(191), nullable=True)

    # The API representation of the object at the time the transaction is
    # generated.
    public_snapshot = Column(BigJSON)
    # Dictionary of any additional properties we wish to snapshot when the
    # transaction is generated.
    private_snapshot = Column(BigJSON)

    def set_extra_attrs(self, obj):
        try:
            self.namespace = obj.namespace
        except AttributeError:
            log.info("Couldn't create {2} revision for {0}:{1}".format(
                self.table_name, self.record_id, self.command))
            log.info("Delta is {0}".format(self.delta))
            log.info("Thread is: {0}".format(obj.thread_id))
            raise
        object_public_id = getattr(obj, 'public_id', None)
        if object_public_id is not None:
            self.object_public_id = object_public_id

    def take_snapshot(self, obj):
        """Record the API's representation of `obj` at the time this
        transaction is generated, as well as any other properties we want to
        have available in the transaction log. Used for client syncing and
        webhooks."""
        from inbox.api.kellogs import encode
        self.public_snapshot = encode(obj)

        from inbox.models.message import Message
        if isinstance(obj, Message):  # hack
            self.private_snapshot = {
                'recentdate': obj.thread.recentdate,
                'subjectdate': obj.thread.subjectdate,
                'filenames': [part.block.filename for part in obj.parts if
                              part.is_attachment]}

Index('namespace_id_deleted_at', Transaction.namespace_id,
      Transaction.deleted_at)

HasRevisions = gen_rev_role(Transaction)
