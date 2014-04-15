"""is_created column in Message table

Revision ID: 13102e0e6fbd
Revises: 193802835c33
Create Date: 2014-04-15 02:35:37.375250

"""

# revision identifiers, used by Alembic.
revision = '13102e0e6fbd'
down_revision = '193802835c33'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('message', sa.Column('is_created', sa.Boolean(),
                                       server_default='false', nullable=True))


def downgrade():
    op.drop_column('message', 'is_created')
