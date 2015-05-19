"""create index for querying messages by namespace and is_created

Revision ID: 576f5310e8fc
Revises: 3d4f5741e1d7
Create Date: 2015-05-19 15:47:16.760020

"""

# revision identifiers, used by Alembic.
revision = '576f5310e8fc'
down_revision = '3d4f5741e1d7'

from alembic import op


def upgrade():
    op.create_index('ix_message_namespace_id_is_created', 'message',
                    ['namespace_id', 'is_created'], unique=False)


def downgrade():
    op.drop_index('ix_message_namespace_id_is_created', table_name='message')
