"""Add GenericAccount.ssl_required

Revision ID: 3d8b5977eaa8
Revises: 4f8e995d1dba
Create Date: 2016-02-18 21:15:56.703467

"""

# revision identifiers, used by Alembic.
revision = '3d8b5977eaa8'
down_revision = '4f8e995d1dba'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("set @@lock_wait_timeout = 20;"))
    conn.execute(text("set @@foreign_key_checks = 0;"))

    conn.execute(text("ALTER TABLE genericaccount "
                      "ADD COLUMN ssl_required BOOLEAN;"))


def downgrade():
    pass
