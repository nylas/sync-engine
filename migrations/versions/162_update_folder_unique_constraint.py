"""update folder unique constraint

Revision ID: 2235895f313b
Revises: 365071c47fa7
Create Date: 2015-05-12 01:51:34.556738

"""

# revision identifiers, used by Alembic.
revision = '2235895f313b'
down_revision = '365071c47fa7'

from alembic import op


def upgrade():
    op.create_unique_constraint('account_id_2', 'folder',
                                ['account_id', 'name'])
    op.drop_constraint(u'account_id', 'folder', type_='unique')


def downgrade():
    op.create_unique_constraint(u'account_id', 'folder',
                                ['account_id', 'name', 'canonical_name',
                                 'identifier'])
    op.drop_constraint('account_id_2', 'folder', type_='unique')
