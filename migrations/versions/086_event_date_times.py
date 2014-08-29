"""event date times

Revision ID: 1ac03cab7a24
Revises: 294200d809c8
Create Date: 2014-08-26 22:43:40.150894

"""

# revision identifiers, used by Alembic.
revision = '1ac03cab7a24'
down_revision = '294200d809c8'

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
    if 'start_date' in [c['name'] for c in inspector.get_columns('event')]:
        op.drop_column('event', 'start_date')
        op.drop_column('event', 'end_date')


def downgrade():
    pass
