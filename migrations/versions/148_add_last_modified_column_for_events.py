"""add last_modified column for events

Revision ID: 54dcea22a268
Revises: 486c7fa5b533
Create Date: 2015-03-16 23:15:55.908307

"""

# revision identifiers, used by Alembic.
revision = '54dcea22a268'
down_revision = '486c7fa5b533'

from alembic import op
from sqlalchemy.sql import text
import sqlalchemy as sa


def upgrade():
    conn = op.get_bind()
    conn.execute(text("set @@lock_wait_timeout = 20;"))
    conn.execute(text("ALTER TABLE event ADD COLUMN last_modified DATETIME"))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("set @@lock_wait_timeout = 20;"))
    conn.execute(text("ALTER TABLE event DROP COLUMN last_modified"))
