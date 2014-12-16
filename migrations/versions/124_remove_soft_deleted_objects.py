"""remove_soft_deleted_objects

Revision ID: 40ad73aa49df
Revises:3c743bd31ee2
Create Date: 2014-12-15 20:38:02.814619

"""

# revision identifiers, used by Alembic.
revision = '40ad73aa49df'
down_revision = '3c743bd31ee2'

from alembic import op
import sqlalchemy as sa


def upgrade():
    conn = op.get_bind()
    # In practice we only have messages and events with deleted_at set.
    conn.execute('DELETE FROM message WHERE deleted_at IS NOT NULL;')
    conn.execute('DELETE FROM event WHERE deleted_at IS NOT NULL;')


def downgrade():
    pass
