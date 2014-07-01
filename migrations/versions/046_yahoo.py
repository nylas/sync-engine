"""yahoo

Revision ID: 38d78543f8be
Revises: 247cd689758c
Create Date: 2014-06-30 18:20:34.960236

"""

# revision identifiers, used by Alembic.
revision = '38d78543f8be'
down_revision = '7a117720554'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('yahooaccount',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.ForeignKeyConstraint(['id'], [u'imapaccount.id'],
                                            ondelete='CASCADE'),
                    sa.Column('password', sa.String(256)),
                    sa.PrimaryKeyConstraint('id')
                    )


def downgrade():
    op.drop_table('yahooaccount')
