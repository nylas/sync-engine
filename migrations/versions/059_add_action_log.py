"""Add action log

Revision ID: 15dfc756a1b0
Revises:4af5952e8a5b
Create Date: 2014-06-26 02:18:24.575796

"""

# revision identifiers, used by Alembic.
revision = '15dfc756a1b0'
down_revision = '4af5952e8a5b'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        'actionlog',
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('namespace_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.Text(length=40), nullable=False),
        sa.Column('record_id', sa.Integer(), nullable=False),
        sa.Column('table_name', sa.Text(length=40), nullable=False),
        sa.ForeignKeyConstraint(['namespace_id'], ['namespace.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_actionlog_created_at', 'actionlog', ['created_at'],
                    unique=False)
    op.create_index('ix_actionlog_deleted_at', 'actionlog', ['deleted_at'],
                    unique=False)
    op.create_index('ix_actionlog_namespace_id', 'actionlog', ['namespace_id'],
                    unique=False)
    op.create_index('ix_actionlog_updated_at', 'actionlog', ['updated_at'],
                    unique=False)


def downgrade():
    op.drop_constraint('actionlog_ibfk_1', 'actionlog',
                       type_='foreignkey')
    op.drop_index('ix_actionlog_updated_at', table_name='actionlog')
    op.drop_index('ix_actionlog_namespace_id', table_name='actionlog')
    op.drop_index('ix_actionlog_deleted_at', table_name='actionlog')
    op.drop_index('ix_actionlog_created_at', table_name='actionlog')
    op.drop_table('actionlog')
