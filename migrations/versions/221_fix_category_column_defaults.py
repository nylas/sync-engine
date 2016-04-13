"""Fix Category column defaults.

Revision ID: 516024977fc5
Revises: 59e1cc690da9
Create Date: 2016-04-13 00:05:16.542436

"""

# revision identifiers, used by Alembic.
revision = '516024977fc5'
down_revision = '59e1cc690da9'

from alembic import op
import sqlalchemy as text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("set @@lock_wait_timeout = 20;"))

    conn.execute(text("ALTER TABLE category "
                      "MODIFY COLUMN name VARCHAR(191) NOT NULL DEFAULT '', "
                      "MODIFY COLUMN deleted_at DATETIME NOT NULL DEFAULT '1970-01-01 00:00:00'"))

    conn.execute(text("ALTER TABLE folder "
                      "MODIFY COLUMN name VARCHAR(191) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL, "
                      "MODIFY COLUMN canonical_name VARCHAR(191) NOT NULL DEFAULT '', "
                      "DROP INDEX account_id, "
                      "ADD CONSTRAINT UNIQUE account_id (account_id, name, canonical_name)"))

    conn.execute(text("ALTER TABLE label "
                      "MODIFY COLUMN canonical_name VARCHAR(191) NOT NULL DEFAULT ''"))


def downgrade():
    pass
