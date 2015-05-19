"""Add public ids to transactions

Revision ID: 1edbd63582c2
Revises: 1d7374c286c5
Create Date: 2014-05-20 23:31:48.924200

"""

# revision identifiers, used by Alembic.
revision = '1edbd63582c2'
down_revision = '1d7374c286c5'

import sys
from gc import collect as garbage_collect
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.ext.declarative import declarative_base


def upgrade():
    op.add_column('transaction',
                  sa.Column('public_id', mysql.BINARY(16), nullable=True))
    op.add_column('transaction',
                  sa.Column('object_public_id', sa.String(length=191),
                            nullable=True))
    op.create_index('ix_transaction_public_id', 'transaction', ['public_id'],
                    unique=False)

    from inbox.sqlalchemy_ext.util import generate_public_id, b36_to_bin
    # TODO(emfree) reflect
    from inbox.models.session import session_scope
    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
    Base = declarative_base()
    Base.metadata.reflect(engine)

    class Transaction(Base):
        __table__ = Base.metadata.tables['transaction']

    with session_scope(versioned=False) as db_session:
        count = 0
        num_transactions, = db_session.query(sa.func.max(Transaction.id)).one()
        print 'Adding public ids to {} transactions'.format(num_transactions)
        for pointer in range(0, num_transactions + 1, 500):
            for entry in db_session.query(Transaction).filter(
                    Transaction.id >= pointer,
                    Transaction.id < pointer + 500):
                entry.public_id = b36_to_bin(generate_public_id())
                count += 1
                if not count % 500:
                    sys.stdout.write('.')
                    sys.stdout.flush()
                    db_session.commit()
                    garbage_collect()

    op.alter_column('transaction', 'public_id',
                    existing_type=mysql.BINARY(16), nullable=False)

    op.add_column('transaction', sa.Column('public_snapshot',
                                           sa.Text(length=4194304),
                                           nullable=True))
    op.add_column('transaction', sa.Column('private_snapshot',
                                           sa.Text(length=4194304),
                                           nullable=True))
    op.drop_column('transaction', u'additional_data')


def downgrade():
    op.drop_index('ix_transaction_public_id', table_name='transaction')
    op.drop_column('transaction', 'public_id')
    op.drop_column('transaction', 'object_public_id')
    op.add_column('transaction', sa.Column(u'additional_data',
                                           mysql.LONGTEXT(), nullable=True))
    op.drop_column('transaction', 'public_snapshot')
    op.drop_column('transaction', 'private_snapshot')
