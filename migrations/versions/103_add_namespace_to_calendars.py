"""add_namespace_to_calendars

Revision ID: 4015edc83ba
Revises:4d10bc835f44
Create Date: 2014-09-22 03:29:21.076836

"""

# revision identifiers, used by Alembic.
revision = '4015edc83ba'
down_revision = '4d10bc835f44'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


def upgrade():
    op.add_column('calendar', sa.Column('namespace_id', sa.Integer(),
                                        sa.ForeignKey('namespace.id')))

    conn = op.get_bind()
    conn.execute(text('''
        UPDATE calendar JOIN namespace ON calendar.account_id=namespace.account_id
        SET calendar.namespace_id=namespace.id'''))

    op.drop_constraint('calendar_ibfk_1', 'calendar', type_='foreignkey')
    op.drop_constraint(u'uuid', 'calendar', type_='unique')
    op.create_unique_constraint('uuid', 'calendar', ['namespace_id',
                                                     'provider_name', 'name'])
    op.drop_column('calendar', 'account_id')


def downgrade():
    raise Exception()
