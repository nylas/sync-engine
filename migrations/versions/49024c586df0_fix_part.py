"""fix part

Revision ID: 49024c586df0
Revises: 112c4df2c65
Create Date: 2015-02-23 17:46:52.791787

"""

# revision identifiers, used by Alembic.
revision = '49024c586df0'
down_revision = '112c4df2c65'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE part MODIFY block_id int(11) DEFAULT NULL"))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE part MODIFY block_id int(11) NOT NULL"))
