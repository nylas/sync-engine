"""Change transaction.object_type to ENUM

Revision ID: 5769d66fb9f2
Revises: 29a1f2ef5653
Create Date: 2016-05-24 23:34:49.815027

"""

# revision identifiers, used by Alembic.
revision = '5769d66fb9f2'
down_revision = '29a1f2ef5653'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE transaction "
                      "MODIFY COLUMN object_type ENUM('account', 'calendar', "
                      "'contact', 'draft', 'event', 'file', 'folder', "
                      "'label', 'message', 'metadata', 'thread') "
                      "NOT NULL"))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE transaction "
                      "MODIFY COLUMN object_type varchar(20) NOT NULL"))
