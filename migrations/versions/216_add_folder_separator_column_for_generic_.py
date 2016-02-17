"""add folder_separator column for generic imap

Revision ID: 4f8e995d1dba
Revises: 31aae1ecb374
Create Date: 2016-02-02 01:17:24.746355

"""

# revision identifiers, used by Alembic.
revision = '4f8e995d1dba'
down_revision = '4bfecbcc7dbd'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("set @@lock_wait_timeout = 20;"))
    conn.execute(text("""ALTER TABLE genericaccount ADD COLUMN folder_separator varchar(16),
                                                    ADD COLUMN folder_prefix varchar(191);"""))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("set @@lock_wait_timeout = 20;"))
    conn.execute(text("ALTER TABLE genericaccount DROP COLUMN folder_separator, DROP COLUMN folder_prefix"))
