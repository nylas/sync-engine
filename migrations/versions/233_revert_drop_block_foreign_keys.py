"""Revert "Drop Block and Part ForeignKeys"

Revision ID: 569ebe8e383d
Revises: 4a44b06cd53b
Create Date: 2016-10-10 18:26:43.036307

"""

# revision identifiers, used by Alembic.
revision = '569ebe8e383d'
down_revision = '4a44b06cd53b'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE block "
                      "ADD CONSTRAINT block_ibfk_1 FOREIGN KEY "
                      "(namespace_id) REFERENCES namespace(id)"))
    conn.execute(text("ALTER TABLE part "
                      "ADD CONSTRAINT part_ibfk_2 FOREIGN KEY "
                      "(message_id) REFERENCES message(id)"))
    conn.execute(text("ALTER TABLE part "
                      "ADD CONSTRAINT part_ibfk_1 FOREIGN KEY "
                      "(block_id) REFERENCES block(id)"))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE part"
                      " DROP FOREIGN KEY part_ibfk_1"))
    conn.execute(text("ALTER TABLE part"
                      " DROP FOREIGN KEY part_ibfk_2"))
    conn.execute(text("ALTER TABLE block"
                      " DROP FOREIGN KEY block_ibfk_1"))
