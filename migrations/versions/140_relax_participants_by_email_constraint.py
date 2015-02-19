"""relax_participants_by_email_constraint

Revision ID: 3f01a3f1b4cc
Revises: 5305d4ae30b4
Create Date: 2015-02-19 00:06:07.906794

"""

# revision identifiers, used by Alembic.
revision = '3f01a3f1b4cc'
down_revision = '1fd7b3e0b662'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE event MODIFY participants_by_email TEXT;"))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE event MODIFY participants_by_email TEXT NOT NULL;"))
