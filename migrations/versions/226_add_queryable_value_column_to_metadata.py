"""Add queryable value column to Metadata

Revision ID: 2dbf6da0775b
Revises: 25129e0316d4
Create Date: 2016-07-18 23:33:52.050259

"""

# revision identifiers, used by Alembic.
revision = '2dbf6da0775b'
down_revision = '25129e0316d4'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('metadata', sa.Column('queryable_value', sa.BigInteger(),
                                        nullable=True))
    op.create_index(op.f('ix_metadata_queryable_value'), 'metadata',
                    ['queryable_value'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_metadata_queryable_value'), table_name='metadata')
    op.drop_column('metadata', 'queryable_value')
