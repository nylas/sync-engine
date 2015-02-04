"""update_transaction_indices

Revision ID: 3bb4a941639c
Revises: 2b288dc444f
Create Date: 2015-02-03 17:50:51.023445

"""

# revision identifiers, used by Alembic.
revision = '3bb4a941639c'
down_revision = '2b288dc444f'

from alembic import op


def upgrade():
    op.create_index('namespace_id_created_at', 'transaction',
                    ['namespace_id', 'created_at'], unique=False)


def downgrade():
    op.drop_index('namespace_id_created_at', table_name='transaction')
