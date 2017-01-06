from sqlalchemy import Column, Integer, String, Enum, Text, Index, BigInteger, \
    ForeignKey
from sqlalchemy.orm import relationship, backref, validates
from sqlalchemy.schema import UniqueConstraint

from inbox.sqlalchemy_ext.util import MAX_TEXT_CHARS
from inbox.models.mixins import (HasPublicID, HasEmailAddress, HasRevisions,
                                 UpdatedAtMixin, DeletedAtMixin)
from inbox.models.base import MailSyncBase
from inbox.models.message import Message
from inbox.models.namespace import Namespace
from inbox.util.encoding import unicode_safe_truncate


class Contact(MailSyncBase, HasRevisions, HasPublicID, HasEmailAddress,
              UpdatedAtMixin, DeletedAtMixin):
    """Data for a user's contact."""
    API_OBJECT_NAME = 'contact'

    namespace_id = Column(BigInteger, nullable=False, index=True)
    namespace = relationship(
        Namespace,
        primaryjoin='foreign(Contact.namespace_id) == remote(Namespace.id)',
        load_on_pending=True)

    # A server-provided unique ID.
    # NB: We specify the collation here so that the test DB gets setup correctly.
    uid = Column(String(64, collation='utf8mb4_bin'), nullable=False)
    # A constant, unique identifier for the remote backend this contact came
    # from. E.g., 'google', 'eas', 'inbox'
    provider_name = Column(String(64))

    name = Column(Text)

    raw_data = Column(Text)

    # A score to use for ranking contact search results. This should be
    # precomputed to facilitate performant search.
    score = Column(Integer)

    # Flag to set if the contact is deleted in a remote backend.
    # (This is an unmapped attribute, i.e., it does not correspond to a
    # database column.)
    deleted = False

    __table_args__ = (UniqueConstraint('uid', 'namespace_id',
                                       'provider_name'),
                      Index('ix_contact_ns_uid_provider_name',
                            'namespace_id', 'uid', 'provider_name'))

    @validates('raw_data')
    def validate_text_column_length(self, key, value):
        if value is None:
            return None
        return unicode_safe_truncate(value, MAX_TEXT_CHARS)

    @property
    def versioned_relationships(self):
        return ['phone_numbers']

    def merge_from(self, new_contact):
        # This must be updated when new fields are added to the class.
        merge_attrs = ['name', 'email_address', 'raw_data']
        for attr in merge_attrs:
            if getattr(self, attr) != getattr(new_contact, attr):
                setattr(self, attr, getattr(new_contact, attr))


class PhoneNumber(MailSyncBase, UpdatedAtMixin, DeletedAtMixin):
    STRING_LENGTH = 64

    contact_id = Column(BigInteger, index=True)
    contact = relationship(
        Contact,
        primaryjoin='foreign(PhoneNumber.contact_id) == remote(Contact.id)',
        backref=backref('phone_numbers', cascade='all, delete-orphan'))

    type = Column(String(STRING_LENGTH), nullable=True)
    number = Column(String(STRING_LENGTH), nullable=False)


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
    contact_id = Column(BigInteger, primary_key=True)
    message_id = Column(ForeignKey(Message.id, ondelete='CASCADE'),
                        primary_key=True)
    field = Column(Enum('from_addr', 'to_addr',
                        'cc_addr', 'bcc_addr', 'reply_to'))
    # Note: The `cascade` properties need to be a parameter of the backref
    # here, and not of the relationship. Otherwise a sqlalchemy error is thrown
    # when you try to delete a message or a contact.
    contact = relationship(
        Contact,
        primaryjoin='foreign(MessageContactAssociation.contact_id) == '
                    'remote(Contact.id)',
        backref=backref('message_associations', cascade='all, delete-orphan'))
    message = relationship(
        Message,
        backref=backref('contacts', cascade='all, delete-orphan'))
