"""longer event descriptions

Revision ID: 56500282e024
Revises: 41f957b595fc
Create Date: 2015-06-23 18:08:47.266984

"""

# revision identifiers, used by Alembic.
revision = '56500282e024'
down_revision = '41f957b595fc'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


def upgrade():
    op.add_column('event', sa.Column('_description', mysql.LONGTEXT(),
                                     nullable=True))


def downgrade():
    op.drop_column('event', '_description')
