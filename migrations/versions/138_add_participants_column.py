"""add participants column

Revision ID: 5305d4ae30b4
Revises: 1f746c93e8fd
Create Date: 2015-02-17 20:02:51.930086

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text
from sqlalchemy import Column
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '5305d4ae30b4'
down_revision = '1f746c93e8fd'

def upgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE event ADD COLUMN participants LONGTEXT;"))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE event DROP COLUMN participants"))
