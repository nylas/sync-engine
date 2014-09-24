"""make message.namespace_id nonnull

Revision ID: 5a68ac0e3e9
Revises: e27104acb25
Create Date: 2014-09-23 05:08:05.978933

"""

# revision identifiers, used by Alembic.
revision = '5a68ac0e3e9'
down_revision = 'e27104acb25'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.alter_column('message', 'namespace_id', existing_type=sa.Integer(),
                    nullable=False)


def downgrade():
    op.alter_column('message', 'namespace_id', existing_type=sa.Integer(),
                    nullable=True)
