"""drop messagecategory foreign keys

Revision ID: 25129e0316d4
Revises: 29a1f2ef5653
Create Date: 2016-05-26 00:07:08.261977

"""

# revision identifiers, used by Alembic.
revision = '25129e0316d4'
down_revision = '29a1f2ef5653'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE messagecategory"
                      " DROP FOREIGN KEY messagecategory_ibfk_1"))

    conn.execute(text("ALTER TABLE messagecategory"
                      " DROP FOREIGN KEY messagecategory_ibfk_2"))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE messagecategory "
                      "ADD CONSTRAINT messagecategory_ibfk_2 FOREIGN KEY "
                      "(category_id) REFERENCES category(id)"))

    conn.execute(text("ALTER TABLE messagecategory "
                      "ADD CONSTRAINT messagecategory_ibfk_1 FOREIGN KEY "
                      "(message_id) REFERENCES message(id)"))
