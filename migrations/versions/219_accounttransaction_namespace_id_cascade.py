"""accounttransaction namespace_id CASCADE

Revision ID: 2b2205db4964
Revises: 3b1cc8580fc2
Create Date: 2016-02-26 22:37:09.398438

"""

# revision identifiers, used by Alembic.
revision = '2b2205db4964'
down_revision = '3b1cc8580fc2'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("set @@lock_wait_timeout = 20;"))
    conn.execute(text("SET FOREIGN_KEY_CHECKS=0;"))

    conn.execute(text("ALTER TABLE accounttransaction DROP FOREIGN KEY accounttransaction_ibfk_1"))
    conn.execute(text("ALTER TABLE accounttransaction ADD CONSTRAINT accounttransaction_ibfk_1 FOREIGN KEY "
                      "(`namespace_id`) REFERENCES `namespace` (`id`) ON DELETE CASCADE"))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("set @@lock_wait_timeout = 20;"))
    conn.execute(text("SET FOREIGN_KEY_CHECKS=0;"))

    conn.execute(text("ALTER TABLE accounttransaction DROP FOREIGN KEY accounttransaction_ibfk_1"))
    conn.execute(text("ALTER TABLE accounttransaction ADD CONSTRAINT accounttransaction_ibfk_1 FOREIGN KEY "
                      "(`namespace_id`) REFERENCES `namespace` (`id`)"))
