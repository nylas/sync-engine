"""remove storage of access_token

Revision ID: 4e44216e9830
Revises: 161b88c17615
Create Date: 2014-07-02 00:48:38.438393

"""

# revision identifiers, used by Alembic.
revision = '4e44216e9830'
down_revision = '161b88c17615'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.drop_column('gmailaccount', 'access_token')
    op.drop_column('gmailaccount', 'expires_in')
    op.drop_column('gmailaccount', 'token_type')


def downgrade():
    op.add_column('gmailaccount', sa.Column('access_token',
                  sa.String(length=512), nullable=True))
    op.add_column('gmailaccount', sa.Column('expires_in',
                  sa.Integer(), nullable=True))
    op.add_column('gmailaccount', sa.Column('token_type',
                  sa.String(length=64), nullable=True))
