"""add supports_condstore column to generic account

Revision ID: 3c74cbe7882e
Revises: 3c02d8204335
Create Date: 2014-08-06 14:41:01.072742

"""

# revision identifiers, used by Alembic.
revision = '3c74cbe7882e'
down_revision = '3de3979f94bd'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('genericaccount', sa.Column('supports_condstore',
                  sa.Boolean(), nullable=True))


def downgrade():
    op.drop_column('genericaccount', 'supports_condstore')
