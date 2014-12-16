from sqlalchemy import Column, Integer, String, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship, backref, validates
from sqlalchemy.schema import UniqueConstraint

from inbox.util.misc import merge_attr
from inbox.sqlalchemy_ext.util import MAX_TEXT_LENGTH
from inbox.models.mixins import HasPublicID, HasEmailAddress, HasRevisions
from inbox.models.base import MailSyncBase
from inbox.models.message import Message
from inbox.models.namespace import Namespace


class Contact(MailSyncBase, HasRevisions, HasPublicID, HasEmailAddress):
    """Data for a user's contact."""
    API_OBJECT_NAME = 'contact'

    @property
    def should_suppress_transaction_creation(self):
        return self.source == 'remote'

    namespace_id = Column(ForeignKey(Namespace.id, ondelete='CASCADE'),
                          nullable=False)
    namespace = relationship(Namespace, load_on_pending=True)

    # A server-provided unique ID.
    uid = Column(String(64), nullable=False)
    # A constant, unique identifier for the remote backend this contact came
    # from. E.g., 'google', 'eas', 'inbox'
    provider_name = Column(String(64))

    # We essentially maintain two copies of a user's contacts.
    # The contacts with source 'remote' give the contact data as it was
    # immediately after the last sync with the remote provider.
    # The contacts with source 'local' also contain any subsequent local
    # modifications to the data.
    source = Column('source', Enum('local', 'remote'))

    name = Column(Text)
    # phone_number = Column(String(64))

    raw_data = Column(Text)

    # A score to use for ranking contact search results. This should be
    # precomputed to facilitate performant search.
    score = Column(Integer)

    # Flag to set if the contact is deleted in a remote backend.
    # (This is an unmapped attribute, i.e., it does not correspond to a
    # database column.)
    deleted = False

    __table_args__ = (UniqueConstraint('uid', 'source', 'namespace_id',
                                       'provider_name'),)

    @validates('raw_data')
    def validate_length(self, key, value):
        return value if value is None else value[:MAX_TEXT_LENGTH]

    def merge_from(self, base, remote):
        # This must be updated when new fields are added to the class.
        merge_attrs = ['name', 'email_address', 'raw_data']
        for attr in merge_attrs:
            merge_attr(base, remote, self, attr)

    def copy_from(self, src):
        """ Copy fields from src."""
        self.namespace_id = src.namespace_id
        self.namespace = src.namespace
        self.uid = src.uid
        self.name = src.name
        self.email_address = src.email_address
        self.provider_name = src.provider_name
        self.raw_data = src.raw_data


class MessageContactAssociation(MailSyncBase):
    """Association table between messages and contacts.

    Examples
    --------
    If m is a message, get the contacts in the to: field with
    [assoc.contact for assoc in m.contacts if assoc.field == 'to_addr']

    If c is a contact, get messages sent to contact c with
    [assoc.message for assoc in c.message_associations if assoc.field ==
    ...  'to_addr']
    """
    contact_id = Column(Integer, ForeignKey(Contact.id, ondelete='CASCADE'),
                        primary_key=True)
    message_id = Column(Integer, ForeignKey(Message.id, ondelete='CASCADE'),
                        primary_key=True)
    field = Column(Enum('from_addr', 'to_addr', 'cc_addr', 'bcc_addr'))
    # Note: The `cascade` properties need to be a parameter of the backref
    # here, and not of the relationship. Otherwise a sqlalchemy error is thrown
    # when you try to delete a message or a contact.
    contact = relationship(
        Contact,
        backref=backref('message_associations', cascade='all, delete-orphan'))
    message = relationship(
        Message,
        backref=backref('contacts', cascade='all, delete-orphan'))
