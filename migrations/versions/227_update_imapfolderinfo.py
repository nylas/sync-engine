"""Update imapfolderinfo

Revision ID: bbf45fac873
Revises:3583211a4838
Create Date: 2016-07-26 01:34:32.689400

"""

# revision identifiers, used by Alembic.
revision = 'bbf45fac873'
down_revision = '2dbf6da0775b'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('imapfolderinfo', sa.Column('fetchedmax',
                                              sa.Integer(), nullable=True))
    op.add_column('imapfolderinfo', sa.Column('fetchedmin',
                                              sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('imapfolderinfo', 'fetchedmax')
    op.drop_column('imapfolderinfo', 'fetchedmin')
