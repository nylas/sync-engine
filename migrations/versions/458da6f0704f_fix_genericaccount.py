"""fix genericaccount

Revision ID: 458da6f0704f
Revises: 1b3d59a7fc36
Create Date: 2015-02-24 01:35:28.539790

"""

# revision identifiers, used by Alembic.
revision = '458da6f0704f'
down_revision = '1b3d59a7fc36'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE genericaccount MODIFY password_id int(11) NOT NULL"))

def downgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE genericaccount MODIFY password_id int(11)"))
