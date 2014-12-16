from sqlalchemy import Column, Integer, String, ForeignKey, Index, Enum
from sqlalchemy.orm import relationship

from inbox.models.base import MailSyncBase
from inbox.models.mixins import HasPublicID, HasRevisions
from inbox.models.namespace import Namespace
from inbox.sqlalchemy_ext.util import BigJSON


class Transaction(MailSyncBase, HasPublicID):
    """ Transactional log to enable client syncing. """
    # Do delete transactions if their associated namespace is deleted.
    namespace_id = Column(Integer,
                          ForeignKey(Namespace.id, ondelete='CASCADE'),
                          nullable=False)
    namespace = relationship(Namespace)

    object_type = Column(String(20), nullable=False, index=True)
    record_id = Column(Integer, nullable=False, index=True)
    object_public_id = Column(String(191), nullable=False, index=True)
    command = Column(Enum('insert', 'update', 'delete'), nullable=False)
    # The API representation of the object at the time the transaction is
    # generated.
    snapshot = Column(BigJSON, nullable=True)


Index('namespace_id_deleted_at', Transaction.namespace_id,
      Transaction.deleted_at)
Index('object_type_record_id', Transaction.object_type, Transaction.record_id)


def create_revisions(session):
    for obj in session.new:
        # Unlikely that you could have new but also soft-deleted objects, but
        # just in case, handle it.
        # TODO(emfree): remove deleted_at handling
        if obj.deleted_at is None:
            create_revision(obj, session, 'insert')
    for obj in session.dirty:
        if obj.deleted_at is not None:
            create_revision(obj, session, 'delete')
        else:
            create_revision(obj, session, 'update')
    for obj in session.deleted:
        create_revision(obj, session, 'delete')


def create_revision(obj, session, revision_type):
    from inbox.api.kellogs import encode
    assert revision_type in ('insert', 'update', 'delete')
    if (not isinstance(obj, HasRevisions) or
            obj.should_suppress_transaction_creation):
        return
    if revision_type == 'update' and not obj.has_versioned_changes():
        return
    revision = Transaction(command=revision_type, record_id=obj.id,
                           object_type=obj.API_OBJECT_NAME,
                           object_public_id=obj.public_id,
                           namespace_id=obj.namespace.id)
    if revision_type != 'delete':
        revision.snapshot = encode(obj)
    session.add(revision)
