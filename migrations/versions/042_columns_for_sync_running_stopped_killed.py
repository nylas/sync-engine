"""Columns for sync running/stopped/killed

Revision ID: 5a136610b50b
Revises: 29efe152cc00
Create Date: 2014-06-23 23:45:34.546823

"""

# revision identifiers, used by Alembic.
revision = '5a136610b50b'
down_revision = '159609404baf'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('account',
                  sa.Column('sync_state',
                            sa.Enum('running', 'stopped', 'killed'),
                            nullable=True))
    op.add_column('account',
                  sa.Column('sync_start_time', sa.DateTime(), nullable=True))
    op.add_column('account',
                  sa.Column('sync_end_time', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('account', 'sync_state')
    op.drop_column('account', 'sync_start_time')
    op.drop_column('account', 'sync_end_time')
