"""Drop unused timestamp mixins

Revision ID: 539ce0291298
Revises: 361972a1de3e
Create Date: 2016-05-05 17:58:05.637106

"""

# revision identifiers, used by Alembic.
revision = '539ce0291298'
down_revision = '361972a1de3e'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE accounttransaction DROP updated_at,"
                      "DROP deleted_at"))
    conn.execute(text("ALTER TABLE messagecategory DROP updated_at,"
                      "DROP deleted_at"))
    conn.execute(text("ALTER TABLE messagecontactassociation DROP updated_at,"
                      "DROP deleted_at"))
    conn.execute(text("ALTER TABLE thread DROP deleted_at, DROP INDEX"
                      " ix_thread_namespace_id_recentdate_deleted_at"))
    conn.execute(text("ALTER TABLE transaction DROP deleted_at,"
                      "DROP updated_at"))
    if conn.engine.has_table('easdevice'):
        # Run EAS specific migrations
        conn.execute(text("ALTER TABLE easdevice DROP deleted_at,"
                          "DROP updated_at"))


def downgrade():
    conn = op.get_bind()
    op.add_column('transaction', sa.Column('updated_at', mysql.DATETIME(),
                  nullable=False))
    op.add_column('transaction', sa.Column('deleted_at', mysql.DATETIME(),
                  nullable=True))
    op.create_index('ix_transaction_updated_at', 'transaction', ['updated_at'],
                    unique=False)
    op.create_index('ix_transaction_deleted_at', 'transaction', ['deleted_at'],
                    unique=False)

    op.create_index('ix_thread_namespace_id_recentdate_deleted_at', 'thread',
                    ['namespace_id', 'recentdate', 'deleted_at'], unique=False)
    op.add_column('thread', sa.Column('deleted_at', mysql.DATETIME(),
                  nullable=True))
    op.create_index('ix_thread_deleted_at', 'thread', ['deleted_at'],
                    unique=False)

    op.add_column('messagecontactassociation', sa.Column('updated_at',
                  mysql.DATETIME(), nullable=False))
    op.add_column('messagecontactassociation', sa.Column('deleted_at',
                  mysql.DATETIME(), nullable=True))
    op.create_index('ix_messagecontactassociation_updated_at',
                    'messagecontactassociation', ['updated_at'], unique=False)
    op.create_index('ix_messagecontactassociation_deleted_at',
                    'messagecontactassociation', ['deleted_at'], unique=False)

    op.add_column('messagecategory', sa.Column('updated_at', mysql.DATETIME(),
                  nullable=False))
    op.add_column('messagecategory', sa.Column('deleted_at', mysql.DATETIME(),
                  nullable=True))
    op.create_index('ix_messagecategory_updated_at', 'messagecategory',
                    ['updated_at'], unique=False)
    op.create_index('ix_messagecategory_deleted_at', 'messagecategory',
                    ['deleted_at'], unique=False)

    op.add_column('accounttransaction', sa.Column('updated_at', mysql.DATETIME(), nullable=False))
    op.add_column('accounttransaction', sa.Column('deleted_at', mysql.DATETIME(), nullable=True))
    op.create_index('ix_accounttransaction_updated_at', 'accounttransaction', ['updated_at'], unique=False)
    op.create_index('ix_accounttransaction_deleted_at', 'accounttransaction', ['deleted_at'], unique=False)

    if conn.engine.has_table('easdevice'):
        op.add_column('easdevice', sa.Column('updated_at', mysql.DATETIME(), nullable=False))
        op.add_column('easdevice', sa.Column('deleted_at', mysql.DATETIME(), nullable=True))
        op.create_index('ix_easdevice_updated_at', 'easdevice', ['updated_at'], unique=False)
        op.create_index('ix_easdevice_deleted_at', 'easdevice', ['deleted_at'], unique=False)

