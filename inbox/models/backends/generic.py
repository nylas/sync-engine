from sqlalchemy import Column, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from inbox.models.backends.imap import ImapAccount
from inbox.models.secret import Secret

PROVIDER = 'generic'


class GenericAccount(ImapAccount):
    id = Column(ForeignKey(ImapAccount.id, ondelete='CASCADE'),
                primary_key=True)

    provider = Column(String(64))
    supports_condstore = Column(Boolean)

    # Secret
    password_id = Column(ForeignKey(Secret.id, ondelete='CASCADE'),
                         nullable=False)
    secret = relationship('Secret', cascade='all, delete-orphan',
                          single_parent=True, uselist=False)

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

    @property
    def category_type(self):
        return 'folder'

    @property
    def thread_cls(self):
        from inbox.models.backends.imap import ImapThread
        return ImapThread

    @property
    def actionlog_cls(self):
        from inbox.models.action_log import ActionLog
        return ActionLog
