"""add unique account constraint

Revision ID: 13faec74da45
Revises: 1d93c9f9f506
Create Date: 2015-02-02 13:38:21.725739

"""

# revision identifiers, used by Alembic.
revision = '13faec74da45'
down_revision = '1d93c9f9f506'

from alembic import op


def upgrade():
    op.create_unique_constraint('unique_account_address', 'account',
                                ['_canonicalized_address'])


def downgrade():
    op.drop_constraint('unique_account_address', 'account', type_='unique')
