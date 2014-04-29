"""Add references column to message table

Revision ID: 4fd291c6940c
Revises: 563d405d1f99
Create Date: 2014-04-25 00:51:04.825531

"""

# revision identifiers, used by Alembic.
revision = '4fd291c6940c'
down_revision = '2c9f3a06de09'

from alembic import op
import sqlalchemy as sa

from inbox.sqlalchemy.util import JSON


def upgrade():
    op.add_column('message', sa.Column('references', JSON, nullable=True))


def downgrade():
    op.drop_column('message', 'references')
