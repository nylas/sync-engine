""" Change g_thrid as BigInteger instead of string

Revision ID: 297aa1e1acc7
Revises: 217431caacc7
Create Date: 2014-03-05 19:44:58.323666

"""

# revision identifiers, used by Alembic.
revision = '297aa1e1acc7'
down_revision = '217431caacc7'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    op.alter_column('thread', 'g_thrid', type_=mysql.BIGINT)
    op.execute('OPTIMIZE TABLE thread')


def downgrade():
    op.alter_column('thread', 'g_thrid', type_=sa.String(255))
