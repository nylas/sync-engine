"""add new events and calendars flags

Revision ID: 47aec237051e
Revises: 246a6bf050bc
Create Date: 2015-07-08 17:43:01.086439

"""

# revision identifiers, used by Alembic.
revision = '47aec237051e'
down_revision = '246a6bf050bc'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column(
        'gmailaccount',
        sa.Column('last_calendar_list_sync', sa.DateTime())
    )
    op.add_column(
        'gmailaccount',
        sa.Column('gpush_calendar_list_last_ping', sa.DateTime())
    )
    op.add_column(
        'gmailaccount',
        sa.Column('gpush_calendar_list_expiration', sa.DateTime())
    )

    op.add_column(
        'calendar',
        sa.Column('gpush_last_ping', sa.DateTime())
    )
    op.add_column(
        'calendar',
        sa.Column('gpush_expiration', sa.DateTime())
    )


def downgrade():
    op.drop_column('gmailaccount', 'last_calendar_list_sync')
    op.drop_column('gmailaccount', 'gpush_calendar_list_last_ping')
    op.drop_column('gmailaccount', 'gpush_calendar_list_expiration')

    op.drop_column('calendar', 'gpush_last_ping')
    op.drop_column('calendar', 'gpush_expiration')
