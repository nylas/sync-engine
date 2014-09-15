"""fix outlookaccount typo

Revision ID: 63dc7f205da
Revises: 4b07b67498e1
Create Date: 2014-09-15 16:57:45.265778

"""

# revision identifiers, used by Alembic.
revision = '63dc7f205da'
down_revision = '4b07b67498e1'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("""
    UPDATE account SET TYPE='outlookaccount' WHERE type='outlookccount';
    """))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("""
    UPDATE account SET TYPE='outlookccount' WHERE type='outlookaccount';
    """))
