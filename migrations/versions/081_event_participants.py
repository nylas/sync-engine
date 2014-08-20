"""event participants

Revision ID: 1322d3787305
Revises: 4e3e8abea884
Create Date: 2014-08-15 20:53:36.656057

"""

# revision identifiers, used by Alembic.
revision = '1322d3787305'
down_revision = '4e3e8abea884'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        'eventparticipant',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('public_id', sa.BINARY(length=16), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('_raw_address', sa.String(length=191), nullable=True),
        sa.Column('_canonicalized_address', sa.String(length=191),
                  nullable=True),
        sa.Column('status', sa.Enum('yes', 'no', 'maybe', 'awaiting'),
                  default='awaiting', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['event_id'], ['event.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('_raw_address', 'event_id', name='uid'))


def downgrade():
    op.drop_table('eventparticipant')
