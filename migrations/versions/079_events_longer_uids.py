"""events longer uids

Revision ID: 5901bf556d83
Revises: 1c2253a0e997
Create Date: 2014-08-11 23:06:39.737550

"""

# revision identifiers, used by Alembic.
revision = '5901bf556d83'
down_revision = '1c2253a0e997'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base


def upgrade():
    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
    Base = declarative_base()
    Base.metadata.reflect(engine)

    # The model previously didn't reflect the migration, therefore
    # only drop the uid constraint if it exists (created with creat_db
    # vs a migration).
    inspector = sa.inspect(engine)
    if 'uid' in [c['name'] for c in inspector.get_unique_constraints('event')]:
        op.drop_constraint('uid', 'event', type_='unique')

    op.create_unique_constraint('uuid', 'event', ['uid', 'source',
                                'account_id', 'provider_name'])
    op.alter_column('event', 'uid',
                    type_=sa.String(767, collation='ascii_general_ci'))


def downgrade():
    op.drop_constraint('uuid', 'event', type_='unique')
    op.alter_column('event', 'uid',
                    type_=sa.String(64))
    op.create_unique_constraint('uid', 'event', ['uid', 'source',
                                'account_id', 'provider_name'])
