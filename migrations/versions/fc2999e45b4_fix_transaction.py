"""fix transaction

Revision ID: fc2999e45b4
Revises: 1f0f04f5c61a
Create Date: 2015-02-24 01:43:19.650114

"""

# revision identifiers, used by Alembic.
revision = 'fc2999e45b4'
down_revision = '1f0f04f5c61a'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

def upgrade():
    conn = op.get_bind()
    # conn.execute(text("ALTER TABLE transaction MODIFY object_type varchar(20) NOT NULL"))
    # conn.execute(text("ALTER TABLE transaction MODIFY object_public_id varchar(191) NOT NULL"))


def downgrade():
    conn = op.get_bind()
    # conn.execute(text("ALTER TABLE transaction MODIFY object_type` varchar(20)"))
    # conn.execute(text("ALTER TABLE transaction MODIFY object_public_id varchar(191)"))
