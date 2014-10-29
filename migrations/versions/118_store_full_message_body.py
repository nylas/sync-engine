"""store full message body

Revision ID: 58732bb5d14b
Revises: 26911668870a
Create Date: 2014-10-22 17:37:10.712061

"""

# revision identifiers, used by Alembic.
revision = '58732bb5d14b'
down_revision = '26911668870a'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('message', sa.Column('full_body_id',
                                       sa.Integer, nullable=True))
    op.create_foreign_key("full_body_id_fk", "message", "block",
                          ["full_body_id"], ["id"])


def downgrade():
    op.drop_constraint('full_body_id_fk', 'message', type_='foreignkey')
    op.drop_column('message', 'full_body_id')
