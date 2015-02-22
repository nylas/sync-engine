"""fix event

Revision ID: 16a82cbcd24d
Revises: 181cab41ffa7
Create Date: 2015-02-20 23:33:04.552701

"""

# revision identifiers, used by Alembic.
revision = '16a82cbcd24d'
down_revision = '181cab41ffa7'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE event MODIFY uid varchar(767) CHARACTER SET ascii NOT NULL"))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE event MODIFY uid varchar(767) CHARACTER SET ascii DEFAULT NULL"))
