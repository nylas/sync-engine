from sqlalchemy import Column, Integer, String, ForeignKey

from inbox.models.backends.imap import ImapAccount

PROVIDER = 'gmail'


class GmailAccount(ImapAccount):
    id = Column(Integer, ForeignKey(ImapAccount.id, ondelete='CASCADE'),
                primary_key=True)

    __mapper_args__ = {'polymorphic_identity': 'gmailaccount'}

    access_token = Column(String(512))  # Secret
    refresh_token = Column(String(512))  # Secret
    scope = Column(String(512))
    expires_in = Column(Integer)
    token_type = Column(String(64))
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
        return '{0} {1}'.format(self.given_name, self.family_name)

    @property
    def provider(self):
        return PROVIDER
