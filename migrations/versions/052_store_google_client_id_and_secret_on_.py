"""store google client id and secret on gmailaccounts.

Revision ID: 358d0320397f
Revises: 1925c535a52d
Create Date: 2014-07-14 23:52:43.524840

"""

# revision identifiers, used by Alembic.
revision = '358d0320397f'
down_revision = '1925c535a52d'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('gmailaccount', sa.Column('client_id', sa.String(length=256),
                                            nullable=True))
    op.add_column('gmailaccount', sa.Column('client_secret',
                                            sa.String(length=256),
                                            nullable=True))


def downgrade():
    op.drop_column('gmailaccount', 'client_secret')
    op.drop_column('gmailaccount', 'client_id')
