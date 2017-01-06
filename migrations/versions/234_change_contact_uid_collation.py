"""Make Contact.uid collation case sensitive

Revision ID: 53e6a7446c45
Revises: 569ebe8e383d
Create Date: 2016-10-07 22:51:31.495243

"""

# revision identifiers, used by Alembic.
revision = '53e6a7446c45'
down_revision = '569ebe8e383d'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE contact MODIFY uid varchar(64) NOT NULL COLLATE utf8mb4_bin"))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE contact MODIFY uid varchar(64) NOT NULL COLLATE utf8mb4_general_ci"))
