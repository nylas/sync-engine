from inbox.models.base import MailSyncBase

from sqlalchemy import (Column, String, Integer)


class Secret(MailSyncBase):
    """Simple local secrets table."""
    secret = Column(String(255), nullable=False)

    # what type of secret is being stored
    type = Column(Integer(), nullable=False)

    # an access control list corresponding to the r/w permissions for hosts to
    # get/remove this secret
    acl_id = Column(Integer(), nullable=False)
