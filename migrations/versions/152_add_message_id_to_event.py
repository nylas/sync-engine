"""add message column to event

Revision ID: 211e93aff1e1
Revises: 2493281d621
Create Date: 2015-03-20 18:50:29.961734

"""

# revision identifiers, used by Alembic.
revision = '211e93aff1e1'
down_revision = '2f3c8fa3fc3a'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("SET FOREIGN_KEY_CHECKS=0;"))
    conn.execute(text("ALTER TABLE event ADD COLUMN message_id int(11) DEFAULT NULL"))
    conn.execute(text("ALTER TABLE event ADD CONSTRAINT message_ifbk FOREIGN KEY "
                      "(`message_id`) REFERENCES `message` (`id`) ON DELETE CASCADE"))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("SET FOREIGN_KEY_CHECKS=0;"))
    conn.execute(text("ALTER TABLE event DROP FOREIGN KEY message_ifbk"))
    conn.execute(text("ALTER TABLE event DROP COLUMN message_id"))
