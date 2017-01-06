"""Drop Block and Part ForeignKeys

Revision ID: 4265dc58eec6
Revises: 23ff7f0b506d
Create Date: 2016-09-20 20:39:09.078087

"""

# revision identifiers, used by Alembic.
revision = '4265dc58eec6'
down_revision = '23ff7f0b506d'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE part"
                      " DROP FOREIGN KEY part_ibfk_1"))
    conn.execute(text("ALTER TABLE part"
                      " DROP FOREIGN KEY part_ibfk_2"))
    conn.execute(text("ALTER TABLE block"
                      " DROP FOREIGN KEY block_ibfk_1"))


def downgrade():
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
