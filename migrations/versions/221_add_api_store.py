"""add api store

Revision ID: 3337f46708fa
Revises: 59e1cc690da9
Create Date: 2016-05-02 18:03:05.202685

"""

# revision identifiers, used by Alembic.
revision = '3337f46708fa'
down_revision = '59e1cc690da9'

from alembic import op, context
import sqlalchemy as sa
import sqlalchemy.dialects.mysql as my


def upgrade():
    shard_id = int(context.get_x_argument(as_dictionary=True).get('shard_id'))
    namespace_id_type = sa.Integer() if shard_id == 0 else sa.BigInteger()

    op.create_table('apithread',
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),

        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=False),
        sa.Column('public_id', sa.BINARY(length=16), nullable=False),
        sa.Column('namespace_id', namespace_id_type, nullable=False),
        sa.Column('value', my.LONGBLOB(), nullable=False),
        sa.Column('expanded_value', my.LONGBLOB(), nullable=False),

        sa.Column('categories', sa.Text(), nullable=False),
        sa.Column('subject', sa.String(255), nullable=True),

        sa.PrimaryKeyConstraint('id')

        #sa.ForeignKeyConstraint(['namespace_id'], [u'namespace.id'],
            #ondelete='CASCADE') # doesn't work for some reason
    )

    op.create_table('apimessage',
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),

        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=False),
        sa.Column('public_id', sa.BINARY(length=16), nullable=False),
        sa.Column('namespace_id', namespace_id_type, nullable=False),
        sa.Column('value', my.LONGBLOB(), nullable=False),
        sa.Column('expanded_value', my.LONGBLOB(), nullable=False),

        sa.Column('data_sha256', sa.String(255), nullable=True),

        sa.Column('categories', sa.Text(), nullable=False),
        sa.Column('subject', sa.String(255), nullable=True),
        sa.Column('thread_public_id', sa.BINARY(length=16), nullable=False),

        sa.PrimaryKeyConstraint('id')

        #sa.ForeignKeyConstraint(['namespace_id'], [u'namespace.id'],
            #ondelete='CASCADE') # doesn't work for some reason
    )

    op.create_index('ix_apimessage_public_id',
            'apimessage', ['public_id'], unique=True)
    op.create_index('ix_apithread_public_id',
            'apithread', ['public_id'], unique=True)

    conn = op.get_bind()
    increment = (shard_id << 48) + 1
    conn.execute('ALTER TABLE metadata AUTO_INCREMENT={}'.format(increment))


def downgrade():
    op.drop_table('apimessage')
    op.drop_table('apithread')
