"""add sync_email bit to Account

Revision ID: 527bbdc2b0fa
Revises: dbf45fac873
Create Date: 2015-08-21 02:14:27.298023

"""

# revision identifiers, used by Alembic.
revision = '527bbdc2b0fa'
down_revision = 'dbf45fac873'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column(
        'account',
        sa.Column('sync_email', sa.Boolean(), nullable=False,
                  server_default=sa.sql.expression.true())
    )


def downgrade():
    op.drop_column('account', 'sync_email')
