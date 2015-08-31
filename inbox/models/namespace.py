from sqlalchemy import Column, Integer, Enum, ForeignKey, bindparam
from sqlalchemy.orm import relationship, backref

from inbox.models.base import MailSyncBase
from inbox.models.mixins import HasPublicID
from inbox.sqlalchemy_ext.util import bakery


class Namespace(MailSyncBase, HasPublicID):
    """ A way to do grouping / permissions, basically. """
    # NOTE: only root namespaces have account backends
    account_id = Column(Integer,
                        ForeignKey('account.id', ondelete='CASCADE'),
                        nullable=True)
    # really the root_namespace
    account = relationship('Account',
                           lazy='joined',
                           single_parent=True,
                           backref=backref('namespace',
                                           uselist=False,
                                           lazy='joined',
                                           passive_deletes=True,
                                           cascade='all,delete-orphan'),
                           uselist=False)

    # invariant: imapaccount is non-null iff type is root
    type = Column(Enum('root', 'shared_folder'), nullable=False,
                  server_default='root')

    def __str__(self):
        return "{} <{}>".format(self.public_id, self.account.email_address if
                                self.account else '')

    @property
    def email_address(self):
        if self.account is not None:
            return self.account.email_address

    @classmethod
    def from_public_id(cls, public_id, db_session):
        q = bakery(lambda session: session.query(Namespace))
        q += lambda q: q.filter(
            Namespace.public_id == bindparam('public_id'))
        return q(db_session).params(public_id=public_id).one()


