"""Shorten email addresses so they can be indexed by default

Revision ID: 1d7374c286c5
Revises: 21878b1b3d4b
Create Date: 2014-06-06 21:55:51.363742

"""

# revision identifiers, used by Alembic.
revision = '1d7374c286c5'
down_revision = '21878b1b3d4b'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


def upgrade():
    op.alter_column('account', 'email_address', type_=mysql.VARCHAR(191))
    op.alter_column('contact', 'email_address', type_=mysql.VARCHAR(191))

def downgrade():
    op.alter_column('account', 'email_address', type_=mysql.VARCHAR(254))
    op.alter_column('contact', 'email_address', type_=mysql.VARCHAR(191))
