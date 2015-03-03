"""Update Calendar index.

Revision ID: 1c73ca99c03b
Revises: 1d7a72222b7c
Create Date: 2015-02-26 00:50:52.322510

"""

# revision identifiers, used by Alembic.
revision = '1c73ca99c03b'
down_revision = '1d7a72222b7c'

from alembic import op


def upgrade():
    op.drop_constraint('calendar_ibfk_1', 'calendar', type_='foreignkey')
    op.drop_constraint('uuid', 'calendar', type_='unique')
    op.create_index('uuid', 'calendar',
                    ['namespace_id', 'provider_name', 'name', 'uid'], unique=True)
    op.create_foreign_key('calendar_ibfk_1',
                          'calendar', 'namespace',
                          ['namespace_id'], ['id'])


def downgrade():
    op.drop_constraint('calendar_ibfk_1', 'calendar', type_='foreignkey')
    op.drop_constraint('uuid', 'calendar', type_='unique')
    op.create_index('uuid', 'calendar',
                    ['namespace_id', 'provider_name', 'name'], unique=True)
    op.create_foreign_key('calendar_ibfk_1',
                          'calendar', 'namespace',
                          ['namespace_id'], ['id'])
