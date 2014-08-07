"""add thread order column

Revision ID: 3de3979f94bd
Revises: 322c2800c401
Create Date: 2014-07-25 15:38:30.254843

"""

# revision identifiers, used by Alembic.
revision = '3de3979f94bd'
down_revision = '3c02d8204335'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column("message", sa.Column('thread_order', sa.Integer,
                                       nullable=False))


def downgrade():
    op.drop_column('message', 'thread_order')
