"""Store Message.to_addr as BigJSON.

We expand rather than truncating because it may be used in sending.

Revision ID: 15f7a25f8048
Revises: 31dc0411eecf
Create Date: 2014-09-04 01:17:29.233778

"""

# revision identifiers, used by Alembic.
revision = '15f7a25f8048'
down_revision = '31dc0411eecf'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # Our BigJSON is really a Text(4194304)
    op.alter_column('message', 'to_addr', type_=sa.Text(4194304),
                    existing_nullable=False)


def downgrade():
    # Our JSON is really a Text()
    op.alter_column('message', 'to_addr', type_=sa.Text(),
                    existing_nullable=False)
