"""At Thread.deleted_at

Revision ID: 4a44b06cd53b
Revises: c48fc8dea1b
Create Date: 2016-09-30 21:37:00.824566

"""

# revision identifiers, used by Alembic.
revision = '4a44b06cd53b'
down_revision = 'c48fc8dea1b'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('thread', sa.Column('deleted_at', sa.DateTime(),
                                        nullable=True))
    op.create_index('ix_thread_namespace_id_deleted_at', 'thread',
                    ['namespace_id', 'deleted_at'], unique=False)


def downgrade():
    op.drop_index('ix_thread_namespace_id_deleted_at', table_name='thread')
    op.drop_column('thread', 'deleted_at')
