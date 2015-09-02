"""drop_sync_raw_data_column

Revision ID: 2e515548043b
Revises: 527bbdc2b0fa
Create Date: 2015-09-01 23:37:44.203784

"""

# revision identifiers, used by Alembic.
revision = '2e515548043b'
down_revision = '527bbdc2b0fa'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


def upgrade():
    op.drop_column('account', 'save_raw_messages')


def downgrade():
    op.add_column('account', sa.Column('save_raw_messages',
                                       mysql.TINYINT(display_width=1),
                                       server_default='1', nullable=True))
