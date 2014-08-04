from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy import event
from inbox.models.backends.imap import ImapAccount
from inbox.models.vault import vault

PROVIDER = 'generic'


class GenericAccount(ImapAccount):
    id = Column(Integer, ForeignKey(ImapAccount.id, ondelete='CASCADE'),
                primary_key=True)

    provider = Column(String(64))
    password_id = Column(Integer())  # Secret

    __mapper_args__ = {'polymorphic_identity': 'genericaccount'}

    @property
    def password(self):
        return vault.get(self.password_id)

    @password.setter
    def password(self, value):
        self.password_id = vault.put(value)

    def verify(self):
        from inbox.auth.generic import verify_account
        return verify_account(self)


@event.listens_for(GenericAccount, 'after_update')
def _after_genericaccount_update(mapper, connection, target):
    """ Hook to cascade delete the refresh_token as it may be remote (and usual
    ORM mechanisms don't apply)."""
    if target.deleted_at:
        vault.remove(target.password_id)
