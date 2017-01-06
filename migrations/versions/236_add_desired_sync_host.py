"""Add Account.desired_sync_host column

Revision ID: 3eb4f30c8ed3
Revises: 34815f9e639c
Create Date: 2016-10-19 23:35:58.866180

"""

# revision identifiers, used by Alembic.
revision = '3eb4f30c8ed3'
down_revision = '34815f9e639c'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE account ADD COLUMN desired_sync_host varchar(255)"))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE account DROP COLUMN desired_sync_host"))
