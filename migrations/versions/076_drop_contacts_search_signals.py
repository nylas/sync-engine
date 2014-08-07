"""drop contacts search signals

Revision ID: 1763103db266
Revises:3de3979f94bd
Create Date: 2014-08-07 04:50:58.382371

"""

# revision identifiers, used by Alembic.
revision = '1763103db266'
down_revision = '3de3979f94bd'

from alembic import op


def upgrade():
    op.drop_table('searchsignal')
    op.drop_table('searchtoken')


def downgrade():
    raise Exception('No rolling back')
