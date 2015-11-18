"""drop

Revision ID: 31aae1ecb374
Revises: 3613ca83ea40
Create Date: 2015-11-18 04:14:50.340067

"""

# revision identifiers, used by Alembic.
revision = '31aae1ecb374'
down_revision = '3613ca83ea40'

from alembic import op


def upgrade():
    op.drop_column('message', 'full_body_id')


def downgrade():
    pass
