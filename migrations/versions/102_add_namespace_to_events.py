"""add_namespace_to_events

Revision ID: 4d10bc835f44
Revises: 3bb01fcc755e
Create Date: 2014-09-22 03:28:18.437679

"""

# revision identifiers, used by Alembic.
revision = '4d10bc835f44'
down_revision = '3bb01fcc755e'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


def upgrade():
    op.add_column('event', sa.Column('namespace_id', sa.Integer(),
                                     sa.ForeignKey('namespace.id')))

    conn = op.get_bind()
    conn.execute(text('''
        UPDATE event JOIN namespace ON event.account_id=namespace.account_id
        SET event.namespace_id=namespace.id'''))

    op.drop_constraint(u'uuid', 'event', type_='unique')
    op.drop_constraint('event_ibfk_1', 'event', type_='foreignkey')
    op.create_unique_constraint('uuid', 'event', ['uid', 'source',
                                                  'namespace_id',
                                                  'provider_name'])
    op.drop_column('event', 'account_id')


def downgrade():
    raise Exception()
