"""remove message.thread_order

Revision ID: 2f3c8fa3fc3a
Revises: 1de526a15c5d
Create Date: 2015-03-23 19:14:05.945773

"""

# revision identifiers, used by Alembic.
revision = '2f3c8fa3fc3a'
down_revision = '1de526a15c5d'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


def upgrade():
    op.drop_column('message', 'thread_order')


def downgrade():
    op.add_column('message', sa.Column('thread_order',
                                       mysql.INTEGER(display_width=11),
                                       nullable=False))
