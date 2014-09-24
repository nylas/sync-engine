"""add_namespace_id_to_message

Revision ID: e27104acb25
Revises:40b533a6f3e1
Create Date: 2014-09-22 00:17:21.265052

"""

# revision identifiers, used by Alembic.
revision = 'e27104acb25'
down_revision = '40b533a6f3e1'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


def upgrade():
    op.add_column('message', sa.Column('namespace_id', sa.Integer(),
                                       sa.ForeignKey('namespace.id')))

    conn = op.get_bind()
    conn.execute(text('''
        UPDATE message INNER JOIN thread ON message.thread_id=thread.id
        SET message.namespace_id = thread.namespace_id'''))


def downgrade():
    op.drop_column('message', 'namespace_id')
