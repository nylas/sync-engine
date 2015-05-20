"""Add reply_to to MessageContactAssociation

Revision ID: 41f957b595fc
Revises: 576f5310e8fc
Create Date: 2015-03-18 17:46:01.393708

"""

# revision identifiers, used by Alembic.
revision = '41f957b595fc'
down_revision = '576f5310e8fc'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    op.alter_column('messagecontactassociation', 'field',
                    existing_type=sa.Enum('from_addr', 'to_addr', 'cc_addr', 'bcc_addr'),
                    type_=sa.Enum('from_addr', 'to_addr', 'cc_addr', 'bcc_addr', 'reply_to'))


def downgrade():
    op.alter_column('messagecontactassociation', 'field',
                    existing_type=sa.Enum('from_addr', 'to_addr', 'cc_addr', 'bcc_addr', 'reply_to'),
                    type_=sa.Enum('from_addr', 'to_addr', 'cc_addr', 'bcc_addr'))
