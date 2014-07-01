from sqlalchemy import Column, Integer, String, ForeignKey

from inbox.models.backends.imap import ImapAccount

PROVIDER = 'yahoo'


class YahooAccount(ImapAccount):
    id = Column(Integer, ForeignKey(ImapAccount.id, ondelete='CASCADE'),
                primary_key=True)

    password = Column(String(256))

    __mapper_args__ = {'polymorphic_identity': 'yahooaccount'}

    @property
    def provider(self):
        return PROVIDER
