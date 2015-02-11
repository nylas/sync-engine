"""add actionlog index

Revision ID: 39fa82d3168e
Revises: 4ee8aab06ee
Create Date: 2015-02-11 21:14:14.402620

"""

# revision identifiers, used by Alembic.
revision = '39fa82d3168e'
down_revision = '4ee8aab06ee'

from alembic import op


def upgrade():
    op.create_index('ix_actionlog_status_retries', 'actionlog',
                    ['status', 'retries'], unique=False)


def downgrade():
    op.drop_index('ix_actionlog_status_retries', table_name='actionlog')
