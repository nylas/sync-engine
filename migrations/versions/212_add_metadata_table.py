"""Add metadata table

Revision ID: bc1119471fe
Revises: 31aae1ecb374
Create Date: 2016-01-26 06:01:15.339018

"""

# revision identifiers, used by Alembic.
revision = 'bc1119471fe'
down_revision = '31aae1ecb374'

from alembic import op
import sqlalchemy as sa


def upgrade():
    from inbox.sqlalchemy_ext.util import JSON

    op.create_table(
        'metadata',
        sa.Column('public_id', sa.BINARY(length=16), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('app_id', sa.Integer(), nullable=True),
        sa.Column('app_client_id', sa.BINARY(length=16), nullable=False),
        sa.Column('app_type', sa.String(length=20), nullable=False),
        sa.Column('namespace_id', sa.BigInteger(), nullable=False),
        sa.Column('object_public_id', sa.String(length=191), nullable=False),
        sa.Column('object_type', sa.String(length=20), nullable=False),
        sa.Column('object_id', sa.BigInteger(), nullable=False),
        sa.Column('value', JSON(), nullable=True),
        sa.Column('version', sa.Integer(), server_default='0', nullable=True),
        sa.ForeignKeyConstraint(['namespace_id'], [u'namespace.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_metadata_app_public_id'), 'metadata',
                    ['app_public_id'], unique=False)
    op.create_index(op.f('ix_metadata_created_at'), 'metadata',
                    ['created_at'], unique=False)
    op.create_index(op.f('ix_metadata_deleted_at'), 'metadata',
                    ['deleted_at'], unique=False)
    op.create_index(op.f('ix_metadata_object_id'), 'metadata',
                    ['object_id'], unique=False)
    op.create_index(op.f('ix_metadata_object_public_id'), 'metadata',
                    ['object_public_id'], unique=False)
    op.create_index(op.f('ix_metadata_public_id'), 'metadata',
                    ['public_id'], unique=False)
    op.create_index(op.f('ix_metadata_updated_at'), 'metadata',
                    ['updated_at'], unique=False)
    op.create_index('ix_obj_public_id_app_id', 'metadata',
                    ['object_public_id', 'app_id'], unique=True)


def downgrade():
    op.drop_index('ix_obj_public_id_app_id', table_name='metadata')
    op.drop_index(op.f('ix_metadata_updated_at'), table_name='metadata')
    op.drop_index(op.f('ix_metadata_public_id'), table_name='metadata')
    op.drop_index(op.f('ix_metadata_object_public_id'), table_name='metadata')
    op.drop_index(op.f('ix_metadata_object_id'), table_name='metadata')
    op.drop_index(op.f('ix_metadata_deleted_at'), table_name='metadata')
    op.drop_index(op.f('ix_metadata_created_at'), table_name='metadata')
    op.drop_index(op.f('ix_metadata_app_public_id'), table_name='metadata')
    op.drop_table('metadata')
