"""add more indexes

Revision ID: 118b3cdd0185
Revises: 37cd05edd433
Create Date: 2014-10-01 18:39:45.375318

"""

# revision identifiers, used by Alembic.
revision = '118b3cdd0185'
down_revision = '37cd05edd433'

from alembic import op


def upgrade():
    op.create_index('ix_thread_recentdate', 'thread', ['recentdate'],
                    unique=False)
    op.create_index('ix_thread_subjectdate', 'thread', ['subjectdate'],
                    unique=False)


def downgrade():
    op.drop_index('ix_thread_subjectdate', table_name='thread')
    op.drop_index('ix_thread_recentdate', table_name='thread')
