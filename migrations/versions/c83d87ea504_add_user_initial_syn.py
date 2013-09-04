"""add User.initial_sync_done column

Revision ID: c83d87ea504
Revises: None
Create Date: 2013-09-03 17:30:03.799946

"""

# revision identifiers, used by Alembic.
revision = 'c83d87ea504'
down_revision = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('users', sa.Column('initial_sync_done', sa.Boolean))


def downgrade():
    op.drop_column('users', 'initial_sync_done')
