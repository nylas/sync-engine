from sqlalchemy import Boolean, Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship, backref

from inbox.models.backends.imap import ImapAccount
from inbox.models.backends.oauth import OAuthAccount
from inbox.models.base import MailSyncBase
from inbox.models.secret import Secret

from inbox.log import get_logger
log = get_logger()

PROVIDER = 'gmail'


class GmailAccount(OAuthAccount, ImapAccount):
    id = Column(Integer, ForeignKey(ImapAccount.id, ondelete='CASCADE'),
                primary_key=True)

    __mapper_args__ = {'polymorphic_identity': 'gmailaccount'}

    # STOPSHIP(emfree) store these either as secrets or as properties of the
    # developer app.
    client_id = Column(String(256))
    client_secret = Column(String(256))
    scope = Column(String(512))
    access_type = Column(String(64))
    family_name = Column(String(256))
    given_name = Column(String(256))
    gender = Column(String(16))
    g_id = Column(String(32))  # `id`
    g_id_token = Column(String(1024))  # `id_token`
    g_user_id = Column(String(32))  # `user_id`
    link = Column(String(256))
    locale = Column(String(8))
    picture = Column(String(1024))
    home_domain = Column(String(256))

    @property
    def provider(self):
        return PROVIDER

    @property
    def category_type(self):
        return 'label'

    @property
    def thread_cls(self):
        from inbox.models.backends.imap import ImapThread
        return ImapThread

    @property
    def actionlog_cls(self):
        from inbox.models.action_log import ActionLog
        return ActionLog


class GmailAuthCredentials(MailSyncBase):
    """
    Associate a Gmail Account with a refresh token using a
    one-to-many relationship. Refresh token ids are actually
    ids of objects in the 'secrets' table.

    A GmailAccount has many GmailAuthCredentials.
    A GmailAuthCredentials entry has a single secret.

    If g is a gmail account, you can get all of its refresh tokens w/
    [auth_creds.refresh_token for auth_creds in g.auth_credentials]
    """

    gmailaccount_id = Column(Integer,
                             ForeignKey(GmailAccount.id, ondelete='CASCADE'))
    refresh_token_id = Column(Integer,
                              ForeignKey(Secret.id, ondelete='CASCADE'))

    scopes = Column(String(512))
    g_id_token = Column(String(1024))
    client_id = Column(String(256))
    client_secret = Column(String(256))
    is_valid = Column(Boolean, default=True)

    gmailaccount = relationship(
        GmailAccount,
        backref=backref('auth_credentials', cascade='all, delete-orphan')
    )

    refresh_token_secret = relationship(
        Secret,
        backref=backref('gmail_auth_credentials', cascade='all, delete-orphan')
    )

    @property
    def refresh_token(self):
        if self.refresh_token_secret:
            return self.refresh_token_secret.secret
        return None

    @refresh_token.setter
    def refresh_token(self, value):
        # Must be a valid UTF-8 byte sequence without NULL bytes.
        if isinstance(value, unicode):
            value = value.encode('utf-8')

        try:
            unicode(value, 'utf-8')
        except UnicodeDecodeError:
            raise ValueError('Invalid refresh_token')

        if b'\x00' in value:
            raise ValueError('Invalid refresh_token')

        if not self.refresh_token_secret:
            self.refresh_token_secret = Secret()

        self.refresh_token_secret.secret = value
        self.refresh_token_secret.type = 'token'
