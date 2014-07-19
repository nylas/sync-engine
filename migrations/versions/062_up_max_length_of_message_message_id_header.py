"""Up max length of Message.message_id_header

From http://tools.ietf.org/html/rfc4130 (section 5.3.3),
max message_id_header is 998 characters.
We could get DataErrors otherwise.

Revision ID: 4c03aaa1fa47
Revises: bb4f204f192
Create Date: 2014-07-19 02:05:17.885327

"""

# revision identifiers, used by Alembic.
revision = '4c03aaa1fa47'
down_revision = 'bb4f204f192'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.alter_column('message', 'message_id_header',
                    type_=sa.String(998), existing_nullable=True)


def downgrade():
    op.alter_column('message', 'message_id_header',
                    type_=sa.String(225), existing_nullable=True)
