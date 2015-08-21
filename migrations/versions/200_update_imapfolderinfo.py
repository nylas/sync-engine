"""Update imapfolderinfo

Revision ID: dbf45fac873
Revises:3583211a4838
Create Date: 2015-08-04 01:34:32.689400

"""

# revision identifiers, used by Alembic.
revision = 'dbf45fac873'
down_revision = '3583211a4838'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('imapfolderinfo', sa.Column('last_slow_refresh',
                                              sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('imapfolderinfo', 'last_slow_refresh')
