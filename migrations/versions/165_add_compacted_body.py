"""add compacted body

Revision ID: 29698176aa8d
Revises:17dcbd7754e0
Create Date: 2015-05-06 18:51:12.598129

"""

# revision identifiers, used by Alembic.
revision = '29698176aa8d'
down_revision = '17dcbd7754e0'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


def upgrade():
    op.add_column(u'message', sa.Column('_compacted_body', mysql.LONGBLOB(),
                                        nullable=True))


def downgrade():
    op.drop_column(u'message', '_compacted_body')
