from sqlalchemy import Column, Integer, String, ForeignKey

from inbox.models.backends.imap import ImapAccount

PROVIDER = 'yahoo'
IMAP_HOST = 'imap.mail.yahoo.com'


class YahooAccount(ImapAccount):
    id = Column(Integer, ForeignKey(ImapAccount.id, ondelete='CASCADE'),
                primary_key=True)

    password = Column(String(256))

    __mapper_args__ = {'polymorphic_identity': 'yahooaccount'}

    @property
    def provider(self):
        return PROVIDER

    def verify(self):
        from inbox.auth.imap import verify_account
        return verify_account(self, IMAP_HOST)
