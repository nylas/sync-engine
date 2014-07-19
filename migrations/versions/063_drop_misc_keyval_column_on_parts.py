"""Drop misc_keyval column on parts

We're currently neither using it nor doing length checking, which is
causing problems.

Revision ID: 4fd3fcd46a3b
Revises: 4c03aaa1fa47
Create Date: 2014-07-19 04:26:55.064832

"""

# revision identifiers, used by Alembic.
revision = '4fd3fcd46a3b'
down_revision = '4c03aaa1fa47'

from alembic import op


def upgrade():
    op.drop_column('part', 'misc_keyval')


def downgrade():
    raise Exception("Not supported")
