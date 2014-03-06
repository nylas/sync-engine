"""expand LittleJSON

Revision ID: 269247bc37d3
Revises: 297aa1e1acc7
Create Date: 2014-03-06 19:11:31.079427

"""

# revision identifiers, used by Alembic.
revision = '269247bc37d3'
down_revision = '297aa1e1acc7'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.alter_column('imapuid', 'extra_flags', type_=sa.String(255))

def downgrade():
    op.alter_column('imapuid', 'extra_flags', type_=sa.String(40))
