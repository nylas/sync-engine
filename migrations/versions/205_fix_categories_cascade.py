"""fix_categories_cascade

Revision ID: 302d9f6b22f3
Revises: 420ccbea2c5e
Create Date: 2015-09-08 16:38:15.335787

"""

# revision identifiers, used by Alembic.
revision = '302d9f6b22f3'
down_revision = '583e083d4512'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("set @@lock_wait_timeout = 20;"))
    conn.execute(text("SET FOREIGN_KEY_CHECKS=0;"))

    conn.execute(text("ALTER TABLE folder DROP FOREIGN KEY folder_ibfk_1"))
    conn.execute(text("ALTER TABLE folder ADD CONSTRAINT folder_ibfk_1 FOREIGN KEY "
                      "(`category_id`) REFERENCES `category` (`id`) ON DELETE CASCADE"))

    conn.execute(text("ALTER TABLE label DROP FOREIGN KEY label_ibfk_1"))
    conn.execute(text("ALTER TABLE label ADD CONSTRAINT label_ibfk_1 FOREIGN KEY "
                      "(`category_id`) REFERENCES `category` (`id`) ON DELETE CASCADE"))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("set @@lock_wait_timeout = 20;"))
    conn.execute(text("SET FOREIGN_KEY_CHECKS=0;"))

    conn.execute(text("ALTER TABLE folder DROP FOREIGN KEY folder_ibfk_1"))
    conn.execute(text("ALTER TABLE folder ADD CONSTRAINT folder_ibfk_1 FOREIGN KEY "
                      "(`category_id`) REFERENCES `category` (`id`)"))

    conn.execute(text("ALTER TABLE label DROP FOREIGN KEY label_ibfk_1"))
    conn.execute(text("ALTER TABLE label ADD CONSTRAINT label_ibfk_1 FOREIGN KEY "
                      "(`category_id`) REFERENCES `category` (`id`)"))
