"""add multi-column transaction index

Revision ID: 2e6120c97485
Revises: 2d05e116bdb7
Create Date: 2014-07-20 03:23:21.303491

"""

# revision identifiers, used by Alembic.
revision = '2e6120c97485'
down_revision = '2d05e116bdb7'

from alembic import op


def upgrade():
    op.create_index('namespace_id_deleted_at',
                    'transaction', ['namespace_id', 'deleted_at'],
                    unique=False)


def downgrade():
    op.drop_index('namespace_id_deleted_at', table_name='transaction')
