from sqlalchemy import Column, Integer, String, ForeignKey, BigInteger, Index
from sqlalchemy.orm import (relationship)
from inbox.sqlalchemy_ext.util import JSON

from inbox.models.base import MailSyncBase
from inbox.models.mixins import (HasPublicID, HasRevisions, UpdatedAtMixin,
                                 DeletedAtMixin)
from inbox.sqlalchemy_ext.util import Base36UID
from inbox.models.namespace import Namespace


class Metadata(MailSyncBase, HasPublicID, HasRevisions, UpdatedAtMixin,
               DeletedAtMixin):
    """
    Key-value store for applications to store arbitrary data associated with
    mail. API object public_id's are used as the keys, and values are JSON.
    Beyond JSON validation, datastore has no knowledge of the structure of
    stored data.

    NOTE: One metadata entry can exist per API object per application, and
    that mapping serves as the unique public identifier for the metadata object
    (despite the public ID column). Thus, version numbers need to persist
    through deletions in order to keep clients in sync. This means that
    metadata objects should never be deleted from the table; instead, the row's
    value should be set to null.
    """
    API_OBJECT_NAME = 'metadata'

    # Application data fields
    # - app_id: The referenced app's primary key
    # - app_client_id: the app's public key, used to identify it externally;
    #                  included here so it appears in deltas.
    # - app_type: 'plugin' or 'app', for future use to filter deltas
    app_id = Column(Integer)
    app_client_id = Column(Base36UID, nullable=False)
    app_type = Column(String(20), nullable=False)

    namespace_id = Column(ForeignKey(Namespace.id, ondelete='CASCADE'),
                          nullable=False)
    namespace = relationship(Namespace)

    # Reference to the object that this metadata is about. Public ID is the
    # external identifier, while type and id allow direct lookup of the object.
    object_public_id = Column(String(191), nullable=False, index=True)
    object_type = Column(String(20), nullable=False)
    object_id = Column(BigInteger, nullable=False)

    value = Column(JSON)

    queryable_value = Column(Integer, nullable=True, index=True)

    version = Column(Integer, nullable=True, server_default='0')

Index('ix_obj_public_id_app_id',
      Metadata.object_public_id, Metadata.app_id, unique=True)
Index('ix_namespace_id_app_id',
      Metadata.namespace_id, Metadata.app_id)
