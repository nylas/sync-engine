from sqlalchemy import Column, Integer, String, ForeignKey

from inbox.models.backends.imap import ImapAccount
from inbox.models.backends.oauth import OAuthAccount
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
    name = Column(String(256))
    gender = Column(String(16))
    g_id = Column(String(32))  # `id`
    g_id_token = Column(String(1024))  # `id_token`
    g_user_id = Column(String(32))  # `user_id`
    link = Column(String(256))
    locale = Column(String(8))
    picture = Column(String(1024))
    home_domain = Column(String(256))

    @property
    def sender_name(self):
        return self.name or ''

    @property
    def provider(self):
        return PROVIDER

    @property
    def thread_cls(self):
        from inbox.models.backends.imap import ImapThread
        return ImapThread
