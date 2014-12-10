"""Add easeventuid

Revision ID: 476c5185121b
Revises: 526eefc1d600
Create Date: 2014-12-10 22:03:56.946721

"""

# revision identifiers, used by Alembic.
revision = '476c5185121b'
down_revision = '526eefc1d600'

from alembic import op
import sqlalchemy as sa


def upgrade():
    from inbox.ignition import main_engine
    engine = main_engine()

    if not engine.has_table('easaccount'):
        return

    op.create_table(
        'easeventuid',
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('easaccount_id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('folder_id', sa.Integer(), nullable=False),
        sa.Column('fld_uid', sa.Integer(), nullable=False),
        sa.Column('msg_uid', sa.Integer(), nullable=False),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['easaccount_id'], ['easaccount.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['event_id'], ['event.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['folder_id'], ['folder.id'],
                                ondelete='CASCADE')
    )

    op.create_index('ix_easeventuid_created_at', 'easeventuid',
                    ['created_at'], unique=False)
    op.create_index('ix_easeventuid_updated_at', 'easeventuid',
                    ['updated_at'], unique=False)
    op.create_index('ix_easeventuid_deleted_at', 'easeventuid',
                    ['deleted_at'], unique=False)

    op.create_unique_constraint('uq_folder_id', 'easeventuid',
                                ['folder_id', 'msg_uid', 'easaccount_id'])


def downgrade():
    op.drop_constraint('easeventuid_ibfk_1', 'easeventuid', type_='foreignkey')
    op.drop_constraint('easeventuid_ibfk_2', 'easeventuid', type_='foreignkey')
    op.drop_constraint('easeventuid_ibfk_3', 'easeventuid', type_='foreignkey')
    op.drop_table('easeventuid')
