"""folder separators again

Revision ID: 59e1cc690da9
Revises: 2b2205db4964
Create Date: 2016-03-30 18:04:38.484343

"""

# revision identifiers, used by Alembic.
revision = '59e1cc690da9'
down_revision = '2b2205db4964'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("set @@lock_wait_timeout = 20;"))

    # Check if the folder_separator column is defined or not.
    res = conn.execute(text("SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE "
                            "TABLE_NAME = 'genericaccount' AND COLUMN_NAME "
                            "= 'folder_separator' AND TABLE_SCHEMA = DATABASE()"))

    if res.fetchall() == []:
        # Execute migration only if the field isn't defined yet.
        conn.execute(text("ALTER TABLE genericaccount ADD COLUMN folder_separator varchar(16)"))

    res = conn.execute(text("SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE "
                            "TABLE_NAME = 'genericaccount' AND COLUMN_NAME "
                            "= 'folder_prefix' AND TABLE_SCHEMA = DATABASE()"))

    # Check if the folder_prefix column is defined or not.
    if res.fetchall() == []:
        # Execute migration only if the field isn't defined yet.
        conn.execute(text("ALTER TABLE genericaccount ADD COLUMN folder_prefix varchar(191)"))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("set @@lock_wait_timeout = 20;"))
    conn.execute(text("ALTER TABLE genericaccount DROP COLUMN folder_separator"))
    conn.execute(text("ALTER TABLE genericaccount DROP COLUMN folder_prefix"))
