"""Consolidate account sync status columns

Revision ID: 4f57260602c9
Revises: 5143154fb1a2
Create Date: 2014-07-17 06:07:08.339740

"""

# revision identifiers, used by Alembic.
revision = '4f57260602c9'
down_revision = '4b4c5579c083'

from alembic import op
import sqlalchemy as sa
from bson import json_util


def upgrade():
    from inbox.sqlalchemy_ext.util import JSON, MutableDict
    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
    from inbox.models.session import session_scope
    from sqlalchemy.ext.declarative import declarative_base
    op.add_column('account',
                  sa.Column('_sync_status', MutableDict.as_mutable(JSON()),
                            default={}, nullable=True))

    Base = declarative_base()
    Base.metadata.reflect(engine)

    class Account(Base):
        __table__ = Base.metadata.tables['account']

    with session_scope(versioned=False) \
            as db_session:
        for acct in db_session.query(Account):
            d = dict(sync_start_time=str(acct.sync_start_time),
                     sync_end_time=str(acct.sync_end_time))
            acct._sync_status = json_util.dumps(d)

        db_session.commit()

    op.drop_column('account', 'sync_start_time')
    op.drop_column('account', 'sync_end_time')


def downgrade():
    raise Exception("Clocks don't rewind, we don't undo.")
