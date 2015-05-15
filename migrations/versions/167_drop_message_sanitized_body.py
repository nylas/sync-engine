"""drop message.sanitized_body

Revision ID: 1740b45aa815
Revises: 3d4f5741e1d7
Create Date: 2015-05-14 21:19:36.519124

"""

# revision identifiers, used by Alembic.
revision = '1740b45aa815'
down_revision = '3d4f5741e1d7'

from alembic import op


def upgrade():
    op.drop_column('message', 'sanitized_body')


def downgrade():
    raise Exception()
