"""Remove Message ForeignKeys

Revision ID: 17b147c1d53c
Revises: 2dbf6da0775b
Create Date: 2016-08-22 18:19:12.911710

"""

# revision identifiers, used by Alembic.
revision = '17b147c1d53c'
down_revision = '2dbf6da0775b'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE message"
                      " DROP FOREIGN KEY message_ibfk_1"))
    conn.execute(text("ALTER TABLE message"
                      " DROP FOREIGN KEY message_ibfk_2"))
    conn.execute(text("ALTER TABLE message"
                      " DROP FOREIGN KEY message_ibfk_3"))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE message"
                      "ADD CONSTRAINT message_ibfk_3 FOREIGN KEY "
                      "(reply_to_message_id) REFERENCES message(id)"))
    conn.execute(text("ALTER TABLE message"
                      "ADD CONSTRAINT message_ibfk_2 FOREIGN KEY "
                      "(thread_id) REFERENCES thread(id)"))
    conn.execute(text("ALTER TABLE message"
                      "ADD CONSTRAINT message_ibfk_1 FOREIGN KEY "
                      "(namespace_id) REFERENCES namespace(id)"))
