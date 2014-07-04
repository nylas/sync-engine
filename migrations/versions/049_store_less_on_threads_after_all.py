"""store less on threads after all

Revision ID: 1b751e8d9cac
Revises: 4e44216e9830
Create Date: 2014-07-04 01:06:18.125947

"""

# revision identifiers, used by Alembic.
revision = '1b751e8d9cac'
down_revision = '4e44216e9830'

from alembic import op


def upgrade():
    op.drop_column('thread', 'participants')
    op.drop_column('thread', 'message_public_ids')


def downgrade():
    raise Exception('would not recreate data')
