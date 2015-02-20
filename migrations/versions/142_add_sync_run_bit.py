"""Add sync_should_run bit to Account

Revision ID: 2d8a350b4885
Revises: 3ab34bc85c8d
Create Date: 2015-02-17 19:39:08.096367

"""

# revision identifiers, used by Alembic.
revision = '2d8a350b4885'
down_revision = '3ab34bc85c8d'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('account', sa.Column('sync_should_run', sa.Boolean(),
                  server_default='1', nullable=True))


def downgrade():
    op.drop_column('account', 'sync_should_run')
