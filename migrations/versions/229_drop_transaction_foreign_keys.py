"""Remove Transaction ForeignKeys

Revision ID: 23ff7f0b506d
Revises: 3df39f4fbdec
Create Date: 2016-09-07 19:31:02.396029

"""

# revision identifiers, used by Alembic.
revision = '23ff7f0b506d'
down_revision = '3df39f4fbdec'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE transaction"
                      " DROP FOREIGN KEY transaction_ibfk_1"))
    conn.execute(text("ALTER TABLE accounttransaction"
                      " DROP FOREIGN KEY accounttransaction_ibfk_1"))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE accounttransaction"
                      "ADD CONSTRAINT accounttransaction_ibfk_1 FOREIGN KEY "
                      "(namespace_id) REFERENCES namespace(id)"))
    conn.execute(text("ALTER TABLE transaction"
                      "ADD CONSTRAINT transaction_ibfk_1 FOREIGN KEY "
                      "(namespace_id) REFERENCES namespace(id)"))
