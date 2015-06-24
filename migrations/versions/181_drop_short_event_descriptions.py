"""drop short event descriptions

Revision ID: 10da2e0bc3bb
Revises: ea9dc8742ee
Create Date: 2015-06-23 18:39:53.327467

"""

# revision identifiers, used by Alembic.
revision = '10da2e0bc3bb'
down_revision = 'ea9dc8742ee'

from alembic import op


def upgrade():
    op.drop_column('event', 'description')


def downgrade():
    raise Exception()
