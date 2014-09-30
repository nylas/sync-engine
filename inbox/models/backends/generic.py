from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from inbox.models.backends.imap import ImapAccount
from inbox.models.secret import Secret

PROVIDER = 'generic'


class GenericAccount(ImapAccount):
    id = Column(Integer, ForeignKey(ImapAccount.id, ondelete='CASCADE'),
                primary_key=True)

    provider = Column(String(64))
    supports_condstore = Column(Boolean)

    # Secret
    password_id = Column(Integer, ForeignKey(Secret.id), nullable=False)
    secret = relationship(
        'Secret', uselist=False,
        primaryjoin='and_(GenericAccount.password_id == Secret.id, '
                    'Secret.deleted_at.is_(None))')

    __mapper_args__ = {'polymorphic_identity': 'genericaccount'}

    @property
    def password(self):
        return self.secret.secret

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

        if not self.secret:
            self.secret = Secret()

        self.secret.secret = value
        self.secret.type = 'password'

    def verify(self):
        from inbox.auth.generic import verify_account
        return verify_account(self)

    @property
    def thread_cls(self):
        from inbox.models.backends.imap import ImapThread
        return ImapThread
