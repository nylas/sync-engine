"""Add Message.categories_change_counter

Revision ID: 3cf51fb0e76a
Revises: 691fa97024d
Create Date: 2015-07-23 22:56:25.945108

"""

# revision identifiers, used by Alembic.
revision = '3cf51fb0e76a'
down_revision = '4fa0540482f8'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.alter_column(
        'message', 'state',
        type_=sa.Enum('draft', 'sending', 'sending failed', 'sent',
                      'actions_pending', 'actions_committed'),
        existing_type=sa.Enum('draft', 'sending', 'sending failed', 'sent'))

    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
    if not engine.has_table('easdevice'):
        return
    op.add_column('easdevice',
                  sa.Column('active', sa.Boolean(),
                            server_default=sa.sql.expression.false(),
                            nullable=False))


def downgrade():
    pass
