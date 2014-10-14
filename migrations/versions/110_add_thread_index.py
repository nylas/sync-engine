"""add thread index

Revision ID: 4011b943a24d
Revises: 5709063bff01
Create Date: 2014-10-14 06:09:07.279954

"""

# revision identifiers, used by Alembic.
revision = '4011b943a24d'
down_revision = '5709063bff01'

from alembic import op


def upgrade():
    op.create_index('ix_thread_namespace_id_recentdate_deleted_at', 'thread',
                    ['namespace_id', 'recentdate', 'deleted_at'], unique=False)


def downgrade():
    op.drop_index('ix_thread_namespace_id_recentdate_deleted_at',
                  table_name='thread')
