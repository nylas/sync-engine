"""add account liveness

Revision ID: 4b4674f1a726
Revises: 1925c535a52d
Create Date: 2014-07-15 17:21:31.618746

"""

# revision identifiers, used by Alembic.
revision = '4b4674f1a726'
down_revision = '5143154fb1a2'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column(
        'account',
        sa.Column('state', sa.Enum('live', 'down', 'invalid'), nullable=True))


def downgrade():
    op.drop_column('account', 'state')
