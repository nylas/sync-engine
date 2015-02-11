"""Add composite index to TagItem

Revision ID: 4ee8aab06ee
Revises: 4270a032b943
Create Date: 2015-02-10 00:04:00.832209

"""

# revision identifiers, used by Alembic.
revision = '4ee8aab06ee'
down_revision = '4270a032b943'

from alembic import op


def upgrade():
    op.create_index('tag_thread_ids', 'tagitem', ['thread_id', 'tag_id'])


def downgrade():
    op.drop_index('tag_thread_ids', table_name='tagitem')
