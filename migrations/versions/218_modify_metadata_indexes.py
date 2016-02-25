"""Modify indices on Metadata table

Revision ID: 3b1cc8580fc2
Revises: 3d8b5977eaa8
Create Date: 2016-02-25 02:06:34.718895

"""

# revision identifiers, used by Alembic.
revision = '3b1cc8580fc2'
down_revision = '3d8b5977eaa8'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_index('ix_namespace_id_app_id', 'metadata', ['namespace_id', 'app_id'], unique=False)
    op.drop_index('ix_metadata_object_id', table_name='metadata')


def downgrade():
    op.create_index('ix_metadata_object_id', 'metadata', ['object_id'], unique=False)
    op.drop_index('ix_namespace_id_app_id', table_name='metadata')
