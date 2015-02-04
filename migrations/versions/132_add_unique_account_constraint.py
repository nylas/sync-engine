"""add unique account constraint

Revision ID: 13faec74da45
Revises: 2b288dc444f
Create Date: 2015-02-02 13:38:21.725739

"""

# revision identifiers, used by Alembic.
revision = '13faec74da45'
down_revision = '3bb4a941639c'

from alembic import op


def upgrade():
    op.create_unique_constraint('unique_account_address', 'account',
                                ['_canonicalized_address'])


def downgrade():
    op.drop_constraint('unique_account_address', 'account', type_='unique')
