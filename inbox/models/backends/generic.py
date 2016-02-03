from sqlalchemy import Column, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship, validates

from inbox.models.backends.imap import ImapAccount
from inbox.models.secret import Secret

PROVIDER = 'generic'


class GenericAccount(ImapAccount):
    id = Column(ForeignKey(ImapAccount.id, ondelete='CASCADE'),
                primary_key=True)

    provider = Column(String(64))
    imap_username = Column(String(255), nullable=True)
    smtp_username = Column(String(255), nullable=True)
    supports_condstore = Column(Boolean)

    # IMAP Secret
    imap_password_id = Column(ForeignKey(Secret.id),
                              nullable=False)
    # Cascade on delete would break things if one of these
    # passwords, but not the other, was deleted.
    imap_secret = relationship('Secret', cascade='save-update, merge, '
                                                 'refresh-expire, expunge',
                               single_parent=True, uselist=False,
                               lazy='joined',
                               foreign_keys=[imap_password_id])
    # SMTP Secret
    smtp_password_id = Column(ForeignKey(Secret.id),
                              nullable=False)
    smtp_secret = relationship('Secret', cascade='save-update, merge, '
                                                 'refresh-expire, expunge',
                               single_parent=True, uselist=False,
                               lazy='joined',
                               foreign_keys=[smtp_password_id])
    # Old Secret
    # TODO[logan]: delete once IMAP and SMTP secret are in production.
    password_id = Column(ForeignKey(Secret.id, ondelete='CASCADE'),
                         nullable=True)
    old_secret = relationship('Secret', cascade='all, delete-orphan',
                              single_parent=True, uselist=False,
                              lazy='joined',
                              foreign_keys=[password_id])

    __mapper_args__ = {'polymorphic_identity': 'genericaccount'}

    @property
    def verbose_provider(self):
        if self.provider == 'custom':
            return 'imap'
        return self.provider

    @validates('imap_secret', 'smtp_secret', 'old_secret')
    def valid_password(self, key, value):
        # Must be a valid UTF-8 byte sequence without NULL bytes.
        if isinstance(value, unicode):
            value = value.encode('utf-8')

        try:
            unicode(value, 'utf-8')
        except UnicodeDecodeError:
            raise ValueError('Invalid password')

        if b'\x00' in value:
            raise ValueError('Invalid password')

        return value

    @property
    def imap_password(self):
        return self.imap_secret.secret

    @imap_password.setter
    def imap_password(self, value):
        if not self.imap_secret:
            self.imap_secret = Secret()
        self.imap_secret.secret = value
        self.imap_secret.type = 'password'

    @property
    def smtp_password(self):
        return self.smtp_secret.secret

    @smtp_password.setter
    def smtp_password(self, value):
        if not self.smtp_secret:
            self.smtp_secret = Secret()
        self.smtp_secret.secret = value
        self.smtp_secret.type = 'password'

    # The password property is used for legacy reasons.
    # TODO[logan]: Remove once changeover to IMAP/SMTP auth is complete.
    @property
    def password(self):
        return self.old_secret.secret

    @password.setter
    def password(self, value):
        if not self.old_secret:
            self.old_secret = Secret()
        self.old_secret.secret = value
        self.old_secret.type = 'password'

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
