"""Remove unused indices on transaction table

Revision ID: 361972a1de3e
Revises: 516024977fc5
Create Date: 2016-04-27 20:18:26.123815

"""

# revision identifiers, used by Alembic.
revision = '361972a1de3e'
down_revision = '516024977fc5'

from alembic import op


def upgrade():
    op.drop_index('ix_transaction_table_name', table_name='transaction')
    op.drop_index('namespace_id_deleted_at', table_name='transaction')


def downgrade():
    op.create_index('namespace_id_deleted_at', 'transaction',
                    ['namespace_id', 'deleted_at'], unique=False)
    op.create_index('ix_transaction_table_name', 'transaction',
                    ['object_type'], unique=False)
