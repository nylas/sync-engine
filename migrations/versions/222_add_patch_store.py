"""add patch store

Revision ID: 21b2d3ff0da
Revises: 3337f46708fa
Create Date: 2016-05-06 04:34:02.140121

"""

# revision identifiers, used by Alembic.
revision = '21b2d3ff0da'
down_revision = '3337f46708fa'

from alembic import op, context
import sqlalchemy as sa
import sqlalchemy.dialects.mysql as my


def upgrade():
    shard_id = int(context.get_x_argument(as_dictionary=True).get('shard_id'))
    namespace_id_type = sa.Integer() if shard_id == 0 else sa.BigInteger()

    op.create_table('apipatchthread',
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),

        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=False),
        sa.Column('public_id', sa.BINARY(length=16), nullable=False),
        sa.Column('namespace_id', namespace_id_type, nullable=False),
        sa.Column('value', my.LONGBLOB(), nullable=False),
        sa.Column('expanded_value', my.LONGBLOB(), nullable=False),

        sa.PrimaryKeyConstraint('id')#,

        #sa.ForeignKeyConstraint(['namespace_id'], [u'namespace.id'],
            #ondelete='CASCADE') # doesn't work for some reason
    )

    op.create_table('apipatchmessage',
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),

        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=False),
        sa.Column('public_id', sa.BINARY(length=16), nullable=False),
        sa.Column('namespace_id', namespace_id_type, nullable=False),
        sa.Column('value', my.LONGBLOB(), nullable=False),
        sa.Column('expanded_value', my.LONGBLOB(), nullable=False),

        sa.PrimaryKeyConstraint('id')#,

        #sa.ForeignKeyConstraint(['namespace_id'], [u'namespace.id'],
            #ondelete='CASCADE') # doesn't work for some reason
    )

    op.create_index('ix_apipatchmessage_public_id',
            'apipatchmessage', ['public_id'], unique=True)
    op.create_index('ix_apipatchthread_public_id',
            'apipatchthread', ['public_id'], unique=True)

    conn = op.get_bind()
    increment = (shard_id << 48) + 1
    conn.execute('ALTER TABLE metadata AUTO_INCREMENT={}'.format(increment))


def downgrade():
    op.drop_table('apipatchmessage')
    op.drop_table('apipatchthread')
