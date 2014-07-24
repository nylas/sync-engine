"""aol

Revision ID: 479b3b84a73e
Revises: 1ceff61ec112
Create Date: 2014-07-22 17:08:39.477001

"""

# revision identifiers, used by Alembic.
revision = '479b3b84a73e'
down_revision = '1ceff61ec112'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('aolaccount',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.ForeignKeyConstraint(['id'], [u'imapaccount.id'],
                                            ondelete='CASCADE'),
                    sa.Column('password', sa.String(256)),
                    sa.PrimaryKeyConstraint('id')
                    )


def downgrade():
    op.drop_table('aolaccount')
