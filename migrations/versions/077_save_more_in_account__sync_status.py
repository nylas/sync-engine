"""Save more in Account._sync_status

Revision ID: 55bdefb458d5
Revises: 3de3979f94bd
Create Date: 2014-08-08 22:00:09.196749

"""

# revision identifiers, used by Alembic.
revision = '55bdefb458d5'
down_revision = '3de3979f94bd'

import sqlalchemy as sa

from inbox.models.session import session_scope
from inbox.models import Account


def upgrade():
    with session_scope(versioned=False, ignore_soft_deletes=False) as \
            db_session:
        num_accounts, = db_session.query(sa.func.max(Account.id)).one()

        if num_accounts is None:
            return

        for index in range(0, num_accounts + 1, 1000):
            print index
            for acct in db_session.query(Account).filter(
                    Account.id >= index,
                    Account.id < index + 1000):

                status = acct._sync_status or {}

                status['id'] = acct.id
                status['email'] = acct.email_address
                status['provider'] = acct.provider
                status['state'] = acct.sync_state
                status['sync_host'] = acct.sync_host

                acct._sync_status = status

                db_session.add(acct)

            db_session.commit()


def downgrade():
    pass
