from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
from sqlalchemy import event
from sqlalchemy.orm.exc import NoResultFound

from inbox.models.session import session_scope
from inbox.models.backends.imap import ImapAccount
from inbox.models.secret import Secret
from inbox.models.util import NotFound

PROVIDER = 'generic'


class GenericAccount(ImapAccount):
    id = Column(Integer, ForeignKey(ImapAccount.id, ondelete='CASCADE'),
                primary_key=True)

    provider = Column(String(64))
    supports_condstore = Column(Boolean)

    # Secret
    password_id = Column(Integer)

    __mapper_args__ = {'polymorphic_identity': 'genericaccount'}

    @property
    def password(self):
        with session_scope() as db_session:
            try:
                secret = db_session.query(Secret).filter(
                    Secret.id == self.password_id).one()
                return secret.secret
            except NoResultFound:
                raise NotFound()

    @password.setter
    def password(self, value):
        # Must be a valid UTF-8 byte sequence without NULL bytes.
        if isinstance(value, unicode):
            value = value.encode('utf-8')

        try:
            unicode(value, 'utf-8')
        except UnicodeDecodeError:
            raise ValueError('Invalid password')

        if b'\x00' in value:
            raise ValueError('Invalid password')

        #TODO[k]: Session should not be grabbed here
        with session_scope() as db_session:
            secret = Secret()
            secret.secret = value
            secret.type = 'password'

            db_session.add(secret)
            db_session.commit()

            self.password_id = secret.id

    def verify(self):
        from inbox.auth.generic import verify_account
        return verify_account(self)


@event.listens_for(GenericAccount, 'after_update')
def _after_genericaccount_update(mapper, connection, target):
    """
    Hook to cascade delete the refresh_token as it may be remote (and usual
    ORM mechanisms don't apply).

    """
    if target.deleted_at:
        with session_scope() as db_session:
            try:
                secret = db_session.query(Secret).filter(
                    Secret.id == target.password_id).one()

                db_session.delete(secret)
                db_session.commit()
            except NoResultFound:
                pass
