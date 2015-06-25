"""add data processing cache table

Revision ID: 3857f395fb1d
Revises: 10da2e0bc3bb
Create Date: 2015-06-17 17:53:13.049138

"""

# revision identifiers, used by Alembic.
revision = '3857f395fb1d'
down_revision = '10da2e0bc3bb'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


def upgrade():
    op.create_table(
        'dataprocessingcache',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('namespace_id', sa.Integer(), nullable=False),
        sa.Column('contact_rankings', mysql.MEDIUMBLOB(), nullable=True),
        sa.Column('contact_rankings_last_updated', sa.DateTime(),
                   nullable=True),
        sa.Column('contact_groups', mysql.MEDIUMBLOB(), nullable=True),
        sa.Column('contact_groups_last_updated', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['namespace_id'], [u'namespace.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('namespace_id')
    )


def downgrade():
    op.drop_table('dataprocessingcache')
