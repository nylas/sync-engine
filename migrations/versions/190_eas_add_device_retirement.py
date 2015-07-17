"""eas_add_device_retirement

Revision ID: 246a6bf050bc
Revises: 3b093f2d7419
Create Date: 2015-07-17 02:46:47.842573

"""

# revision identifiers, used by Alembic.
revision = '246a6bf050bc'
down_revision = '3b093f2d7419'

from alembic import op
import sqlalchemy as sa


def upgrade():
    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
    if not engine.has_table('easdevice'):
        return
    op.add_column('easdevice',
                  sa.Column('retired', sa.Boolean(),
                            server_default=sa.sql.expression.false(),
                            nullable=False))


def downgrade():
    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
    if not engine.has_table('easdevice'):
        return
    op.drop_column('easdevice', 'retired')
