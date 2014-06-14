from sqlalchemy import Column, Integer, String, Enum, ForeignKey
from sqlalchemy.orm import relationship, backref

from inbox.models.base import MailSyncBase


class SearchToken(MailSyncBase):
    """A token to prefix-match against for contacts search.
    Right now these tokens consist of:
    - the contact's full name
    - the elements of the contact's name when split by whitespace
    - the contact's email address.
    """
    token = Column(String(255))
    source = Column('source', Enum('name', 'email_address'))
    contact_id = Column(ForeignKey('contact.id', ondelete='CASCADE'))
    contact = relationship(
        'Contact', backref=backref('token',
                                   primaryjoin='and_('
                                   'Contact.id == SearchToken.contact_id, '
                                   'SearchToken.deleted_at.is_(None))'),
        cascade='all',
        primaryjoin='and_(SearchToken.contact_id == Contact.id, '
                    'Contact.deleted_at.is_(None))',
        single_parent=True)


class SearchSignal(MailSyncBase):
    """Represents a signal used for contacts search result ranking. Examples of
    signals might include number of emails sent to or received from this
    contact, or time since last interaction with the contact."""
    name = Column(String(40))
    value = Column(Integer)
    contact_id = Column(ForeignKey('contact.id', ondelete='CASCADE'),
                        nullable=False)
