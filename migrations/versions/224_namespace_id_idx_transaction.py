"""Add namespace_id index on transaction table

Revision ID: 29a1f2ef5653
Revises: 539ce0291298
Create Date: 2016-05-24 00:16:24.965607

"""

# revision identifiers, used by Alembic.
revision = '29a1f2ef5653'
down_revision = '539ce0291298'

from alembic import op


def upgrade():
    op.create_index('idx_namespace', 'transaction', ['namespace_id'],
                    unique=False)


def downgrade():
    op.drop_index('idx_namespace', table_name='transaction')
