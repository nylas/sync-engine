"""add subject indexes

Revision ID: 37cd05edd433
Revises: 569b9d365295
Create Date: 2014-09-30 01:37:18.468317

"""

# revision identifiers, used by Alembic.
revision = '37cd05edd433'
down_revision = '569b9d365295'

from alembic import op


def upgrade():
    op.create_index('ix_message_subject', 'message', ['subject'], unique=False)
    op.create_index('ix_thread_subject', 'thread', ['subject'], unique=False)


def downgrade():
    op.drop_index('ix_thread_subject', table_name='thread')
    op.drop_index('ix_message_subject', table_name='message')
