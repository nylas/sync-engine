"""Message UIDs should be Integers.

Revision ID: 4323056c0b78
Revises: 424b0c9dc77
Create Date: 2013-10-05 19:43:58.504580

"""

# revision identifiers, used by Alembic.
revision = '4323056c0b78'
down_revision = '424b0c9dc77'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.alter_column('foldermeta', 'msg_uid', type_=sa.Integer)


def downgrade():
    op.alter_column('foldermeta', 'msg_uid', type_=sa.String(255))
