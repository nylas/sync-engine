"""add searchindexcursor.

Revision ID: 526eefc1d600
Revises: 8c2406df6f8
Create Date: 2014-11-24 22:16:26.353729

"""

# revision identifiers, used by Alembic.
revision = '526eefc1d600'
down_revision = '8c2406df6f8'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        'searchindexcursor',
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('transaction_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['transaction_id'], ['transaction.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_index('ix_searchindexcursor_created_at', 'searchindexcursor',
                    ['created_at'], unique=False)
    op.create_index('ix_searchindexcursor_deleted_at', 'searchindexcursor',
                    ['deleted_at'], unique=False)
    op.create_index('ix_searchindexcursor_updated_at', 'searchindexcursor',
                    ['updated_at'], unique=False)
    op.create_index('ix_searchindexcursor_transaction_id', 'searchindexcursor',
                    ['transaction_id'], unique=False)


def downgrade():
    op.drop_constraint('searchindexcursor_ibfk_1', 'searchindexcursor',
                       type_='foreignkey')
    op.drop_table('searchindexcursor')
