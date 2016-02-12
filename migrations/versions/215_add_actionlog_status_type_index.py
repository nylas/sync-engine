"""add actionlog (status, type) index

Revision ID: 4bfecbcc7dbd
Revises: 4b83e064dd49
Create Date: 2016-02-11 16:49:20.765262

"""

# revision identifiers, used by Alembic.
revision = '4bfecbcc7dbd'
down_revision = '4b83e064dd49'

from alembic import op


def upgrade():
    op.create_index('idx_status_type', 'actionlog', ['status', 'type'],
                    unique=False)


def downgrade():
    op.drop_index('idx_status_type', table_name='actionlog')
