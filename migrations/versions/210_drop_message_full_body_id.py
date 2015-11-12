"""Drop Message.full_body_id

Revision ID: 3613ca83ea40
Revises: 3618838f5bc6
Create Date: 2015-11-12 00:21:02.683861

"""

# revision identifiers, used by Alembic.
revision = '3613ca83ea40'
down_revision = '3618838f5bc6'

from alembic import op


def upgrade():
    op.drop_constraint(u'full_body_id_fk', 'message', type_='foreignkey')
    op.drop_column('message', 'full_body_id')


def downgrade():
    pass
