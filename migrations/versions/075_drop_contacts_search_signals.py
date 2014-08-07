"""drop contacts search signals

Revision ID: 1763103db266
Revises: 3c02d8204335
Create Date: 2014-08-07 04:50:58.382371

"""

# revision identifiers, used by Alembic.
revision = '1763103db266'
down_revision = '3c02d8204335'

from alembic import op


def upgrade():
    op.drop_table('searchsignal')
    op.drop_table('searchtoken')


def downgrade():
    raise Exception('No rolling back')
