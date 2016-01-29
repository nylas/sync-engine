"""Introduce AccountTransaction.

Revision ID: 4b83e064dd49
Revises: 31aae1ecb374
Create Date: 2016-01-29 22:31:12.638080

"""

# revision identifiers, used by Alembic.
revision = '4b83e064dd49'
down_revision = 'bc1119471fe'

from alembic import op, context
import sqlalchemy as sa


def upgrade():
    shard_id = int(context.get_x_argument(as_dictionary=True).get('shard_id'))
    namespace_id_type = sa.Integer() if shard_id == 0 else sa.BigInteger()

    op.create_table('accounttransaction',
                    sa.Column('created_at', sa.DateTime(), nullable=False),
                    sa.Column('updated_at', sa.DateTime(), nullable=False),
                    sa.Column('deleted_at', sa.DateTime(), nullable=True),
                    sa.Column('id', sa.BigInteger(), nullable=False),
                    sa.Column('public_id', sa.BINARY(length=16), nullable=False),
                    sa.Column('namespace_id', namespace_id_type, nullable=True),
                    sa.Column('object_type', sa.String(20), nullable=False),
                    sa.Column('record_id', sa.BigInteger(), nullable=False),
                    sa.Column('object_public_id', sa.String(191), nullable=False),
                    sa.Column('command', sa.Enum('insert', 'update', 'delete'),
                              nullable=False),
                    sa.PrimaryKeyConstraint('id'),
                    sa.ForeignKeyConstraint(['namespace_id'],
                                            [u'namespace.id'],)
                    )
    op.create_index('ix_accounttransaction_created_at',
                    'accounttransaction', ['created_at'], unique=False)
    op.create_index('ix_accounttransaction_updated_at',
                    'accounttransaction', ['updated_at'], unique=False)
    op.create_index('ix_accounttransaction_deleted_at',
                    'accounttransaction', ['deleted_at'], unique=False)
    op.create_index('ix_accounttransaction_table_name',
                    'accounttransaction', ['object_type'], unique=False)
    op.create_index('ix_accounttransaction_command',
                    'accounttransaction', ['command'], unique=False)
    op.create_index('ix_accounttransaction_object_type_record_id',
                    'accounttransaction', ['object_type', 'record_id'], unique=False)
    op.create_index('ix_accounttransaction_namespace_id_created_at',
                    'accounttransaction', ['namespace_id', 'created_at'], unique=False)

    conn = op.get_bind()
    increment = (shard_id << 48) + 1
    conn.execute('ALTER TABLE accounttransaction AUTO_INCREMENT={}'.format(increment))


def downgrade():
    pass
