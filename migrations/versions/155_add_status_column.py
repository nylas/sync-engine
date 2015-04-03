"""add status column

Revision ID: 7de8a6ce8cd
Revises: 1f06c15ae796
Create Date: 2015-03-30 12:48:15.317896

"""

# revision identifiers, used by Alembic.
revision = '7de8a6ce8cd'
down_revision = '1f06c15ae796'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("set @@lock_wait_timeout = 20;"))
    conn.execute(text("ALTER TABLE event ADD COLUMN `status` "
                      "enum('tentative','confirmed','cancelled') "
                      "DEFAULT 'confirmed'"))
    conn.execute(text("UPDATE event JOIN recurringeventoverride ON "
                      "event.id = recurringeventoverride.id SET status = 'cancelled' "
                      "where recurringeventoverride.cancelled IS TRUE;"))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("set @@lock_wait_timeout = 20;"))
    conn.execute(text("ALTER TABLE event DROP COLUMN status"))
    print "\nNote that you'll have to reset calendar syncs."
