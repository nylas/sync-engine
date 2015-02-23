"""fix imapfolderinfo

Revision ID: 3148ccd8cc9b
Revises: 5767547528d8
Create Date: 2015-02-23 17:23:29.929075

"""

# revision identifiers, used by Alembic.
revision = '3148ccd8cc9b'
down_revision = '5767547528d8'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE imapfolderinfo MODIFY uidvalidity BIGINT(20) NOT NULL"))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE imapfolderinfo MODIFY uidvalidity BIGINT(20) DEFAULT NULL"))
