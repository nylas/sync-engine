"""store label information per-uid

Revision ID: 4634999269
Revises: 5709063bff01
Create Date: 2014-10-14 10:04:58.710015

"""

# revision identifiers, used by Alembic.
revision = '4634999269'
down_revision = '420bf3422c4f'

from alembic import op
import sqlalchemy as sa

from sqlalchemy.sql import text
from inbox.sqlalchemy_ext.util import JSON


def upgrade():
    op.add_column('imapuid', sa.Column('g_labels', JSON(),
                                       nullable=True))

    conn = op.get_bind()
    conn.execute(text("UPDATE imapuid SET g_labels = '[]'"))


def downgrade():
    op.drop_column('imapuid', 'g_labels')
