"""drop cancelled column

Revision ID: 3c7f059a68ba
Revises: 7de8a6ce8cd
Create Date: 2015-04-01 12:24:16.391039

"""

# revision identifiers, used by Alembic.
revision = '3c7f059a68ba'
down_revision = '7de8a6ce8cd'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE recurringeventoverride "
                      "DROP COLUMN cancelled;"))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE recurringeventoverride "
                      "ADD COLUMN cancelled tinyint(1);"))
    print "\nNote that you'll have to reset calendar syncs."
