"""add a retries column to the actionlog

Revision ID: 5709063bff01
Revises: 2f97277cd86d
Create Date: 2014-10-07 10:34:29.302936

"""

# revision identifiers, used by Alembic.
revision = '5709063bff01'
down_revision = '2f97277cd86d'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import text


def upgrade():
    op.add_column('actionlog',
                  sa.Column('retries', sa.Integer, nullable=False,
                            server_default='0'))
    op.add_column('actionlog',
                  sa.Column('status', sa.Enum('pending', 'successful', 'failed'),
                            server_default='pending'))

    conn = op.get_bind()
    conn.execute(text("UPDATE actionlog SET status='successful' WHERE executed is TRUE"))

    op.drop_column('actionlog', u'executed')


def downgrade():
    raise Exception("Can't.")
