"""extra transaction data

Revision ID: 5093433b073
Revises: 3fee2f161614
Create Date: 2014-04-25 23:23:36.442325

"""

# revision identifiers, used by Alembic.
revision = '5093433b073'
down_revision = '3fee2f161614'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('transaction', sa.Column('additional_data', sa.Text(4194304),
                                           nullable=True))


def downgrade():
    op.drop_column('transaction', 'additional_data')
