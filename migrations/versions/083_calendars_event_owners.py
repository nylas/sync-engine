"""calendars, event owners

Revision ID: 10a1129fe685
Revises: 1322d3787305
Create Date: 2014-08-18 21:50:52.175039

"""

# revision identifiers, used by Alembic.
revision = '10a1129fe685'
down_revision = '1322d3787305'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table


def upgrade():
    # remove old events that didn't match foreign key constraints on calendars
    event = table('event')
    op.execute(event.delete())

    op.create_table(
        'calendar',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('public_id', sa.BINARY(length=16), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('uid', sa.String(767, collation='ascii_general_ci'),
                  nullable=False),
        sa.Column('read_only', sa.Boolean(), nullable=False,
                  default=False),
        sa.ForeignKeyConstraint(['account_id'], ['account.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('account_id', 'name', name='uuid')
    )

    op.add_column('account', sa.Column('default_calendar_id', sa.Integer(),
                  nullable=True))

    op.create_foreign_key('default_calendar_ibfk_1',
                          'account', 'calendar',
                          ['default_calendar_id'], ['id'])
    op.add_column('event', sa.Column('calendar_id', sa.Integer(),
                  nullable=False))

    op.create_foreign_key('event_ibfk_2',
                          'event', 'calendar',
                          ['calendar_id'], ['id'])

    op.add_column('event', sa.Column('owner', sa.String(length=255),
                  nullable=True))

    op.add_column('event', sa.Column('is_owner', sa.Boolean(),
                  default=True,
                  nullable=False))

    op.add_column('eventparticipant', sa.Column('guests', sa.Integer(),
                  default=0,
                  nullable=False))

    op.alter_column('eventparticipant', 'status',
                    existing_type=sa.Enum('yes', 'no', 'maybe', 'awaiting'),
                    type_=sa.Enum('yes', 'no', 'maybe', 'noreply'),
                    existing_nullable=False)

    op.drop_column('event', 'locked')
    op.drop_column('event', 'time_zone')
    op.add_column('event', sa.Column('start_date', sa.Date(),
                  nullable=True))
    op.add_column('event', sa.Column('end_date', sa.Date(),
                  nullable=True))
    op.add_column('event', sa.Column('read_only', sa.Boolean(),
                  nullable=False, default=False))


def downgrade():
    op.alter_column('eventparticipant', 'status',
                    existing_type=sa.Enum('yes', 'no', 'maybe', 'noreply'),
                    type_=sa.Enum('yes', 'no', 'maybe', 'awaiting'),
                    existing_nullable=False)
    op.drop_column('event', 'read_only')
    op.add_column('event', sa.Column('locked', sa.Boolean(),
                  nullable=False))
    op.add_column('event', sa.Column('time_zone', sa.Integer(),
                  nullable=False))
    op.drop_constraint('default_calendar_ibfk_1', 'account',
                       type_='foreignkey')
    op.drop_constraint('event_ibfk_2', 'event',
                       type_='foreignkey')
    op.drop_table('calendar')
    op.drop_column('event', 'calendar_id')
    op.drop_column('event', 'start_date')
    op.drop_column('event', 'end_date')
    op.drop_column('event', 'owner')
    op.drop_column('event', 'is_owner')
    op.drop_column('account', 'default_calendar_id')
    op.drop_column('eventparticipant', 'guests')
