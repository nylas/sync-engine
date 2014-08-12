"""events

Revision ID: 1c2253a0e997
Revises: 3c02d8204335
Create Date: 2014-08-07 00:12:40.148311

"""

# revision identifiers, used by Alembic.
revision = '1c2253a0e997'
down_revision = '3c74cbe7882e'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        'event',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uid', sa.String(length=64), nullable=False),
        sa.Column('provider_name', sa.String(length=64), nullable=False),
        sa.Column('public_id', sa.BINARY(length=16), nullable=False),
        sa.Column('raw_data', sa.Text(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('subject', sa.String(length=255), nullable=True),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('location', sa.String(length=255), nullable=True),
        sa.Column('busy', sa.Boolean(), nullable=False),
        sa.Column('locked', sa.Boolean(), nullable=False),
        sa.Column('reminders', sa.String(length=255), nullable=True),
        sa.Column('recurrence', sa.String(length=255), nullable=True),
        sa.Column('start', sa.DateTime(), nullable=False),
        sa.Column('end', sa.DateTime(), nullable=True),
        sa.Column('all_day', sa.Boolean(), nullable=False),
        sa.Column('time_zone', sa.Integer(), nullable=False),
        sa.Column('source', sa.Enum('remote', 'local'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['account.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.add_column('account', sa.Column('last_synced_events', sa.DateTime(),
                  nullable=True))


def downgrade():
    op.drop_table('event')
    op.drop_column('account', 'last_synced_events')
