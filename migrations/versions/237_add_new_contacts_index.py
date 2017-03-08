"""Add new contacts Index

Revision ID: 780b1dabd51
Revises: 3eb4f30c8ed3
Create Date: 2017-02-09 01:50:33.546883

"""

# revision identifiers, used by Alembic.
revision = '780b1dabd51'
down_revision = '3eb4f30c8ed3'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE contact"
                      " ADD INDEX idx_namespace_created(namespace_id, created_at)"))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE contact"
                      " DROP INDEX idx_namespace_created"))
