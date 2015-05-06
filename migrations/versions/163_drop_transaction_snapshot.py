"""drop transaction snapshot

Revision ID: 457164360472
Revises:2235895f313b
Create Date: 2015-05-06 18:31:46.061688

"""

# revision identifiers, used by Alembic.
revision = '457164360472'
down_revision = '2235895f313b'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    op.drop_column(u'transaction', 'snapshot')


def downgrade():
    raise Exception()
