"""Add initial_sync_start/end to Folder

Revision ID: 3b093f2d7419
Revises: 606447e78e7
Create Date: 2015-07-14 10:06:58.545870

"""

# revision identifiers, used by Alembic.
revision = '3b093f2d7419'
down_revision = '606447e78e7'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('folder', sa.Column('initial_sync_end', sa.DateTime(),
                                      nullable=True))
    op.add_column('folder', sa.Column('initial_sync_start', sa.DateTime(),
                                      nullable=True))


def downgrade():
    op.drop_column('folder', 'initial_sync_start')
    op.drop_column('folder', 'initial_sync_end')
