from sqlalchemy import Column, Integer, ForeignKey

from inbox.models.base import MailSyncBase
from inbox.models.transaction import Transaction


class ContactSearchIndexCursor(MailSyncBase):
    """
    Store the id of the last Transaction indexed into CloudSearch.
    Is namespace-agnostic.

    """
    transaction_id = Column(Integer, ForeignKey(Transaction.id),
                            nullable=True, index=True)
