"""add executed status to action log

Revision ID: 322c2800c401
Revises: 4f3a1f6eaee3
Create Date: 2014-07-22 05:57:03.353143

"""

# revision identifiers, used by Alembic.
revision = '322c2800c401'
down_revision = '4f3a1f6eaee3'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # Purge any existing entries.
    op.drop_table('actionlog')
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
        sa.Column('executed', sa.Boolean(), nullable=False,
                  server_default=sa.sql.expression.false()),
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
    op.drop_column('actionlog', 'executed')
