"""change event sync timestamp

Revision ID: 3a58d466f61d
Revises: 3857f395fb1d
Create Date: 2015-07-01 22:26:22.425718

"""

# revision identifiers, used by Alembic.
revision = '3a58d466f61d'
down_revision = '3857f395fb1d'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('calendar', sa.Column('last_synced', sa.DateTime(),
                                        nullable=True))
    conn = op.get_bind()
    conn.execute('''UPDATE calendar
    JOIN namespace ON calendar.namespace_id=namespace.id
    JOIN account ON namespace.account_id=account.id
    JOIN gmailaccount ON account.id=gmailaccount.id
    SET calendar.last_synced=account.last_synced_events
    WHERE account.emailed_events_calendar_id != calendar.id''')


def downgrade():
    op.drop_column('calendar', 'last_synced')
