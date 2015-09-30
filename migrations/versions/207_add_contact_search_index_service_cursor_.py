"""add contact search index service cursor pointer table

Revision ID: 4b225df49747
Revises: gu8eqpm6f2x1n0fg
Create Date: 2015-09-30 14:47:42.028763

"""

# revision identifiers, used by Alembic.
revision = '4b225df49747'
down_revision = 'gu8eqpm6f2x1n0fg'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


def upgrade():
    op.create_table('contactsearchindexcursor',
                    sa.Column('created_at', sa.DateTime(), nullable=False),
                    sa.Column('updated_at', sa.DateTime(), nullable=False),
                    sa.Column('deleted_at', sa.DateTime(), nullable=True),
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('transaction_id', sa.Integer(), nullable=True),
                    sa.ForeignKeyConstraint(['transaction_id'],
                                            [u'transaction.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_index('ix_contactsearchindexcursor_created_at',
                    'contactsearchindexcursor', ['created_at'], unique=False)
    op.create_index('ix_contactsearchindexcursor_deleted_at',
                    'contactsearchindexcursor', ['deleted_at'], unique=False)
    op.create_index('ix_contactsearchindexcursor_transaction_id',
                    'contactsearchindexcursor', ['transaction_id'], unique=False)
    op.create_index('ix_contactsearchindexcursor_updated_at',
                    'contactsearchindexcursor', ['updated_at'], unique=False)
    op.drop_table('searchindexcursor')


def downgrade():
    op.create_table('searchindexcursor',
                    sa.Column('created_at', mysql.DATETIME(), nullable=False),
                    sa.Column('updated_at', mysql.DATETIME(), nullable=False),
                    sa.Column('deleted_at', mysql.DATETIME(), nullable=True),
                    sa.Column('id', mysql.INTEGER(display_width=11), nullable=False),
                    sa.Column('transaction_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=True),
                    sa.ForeignKeyConstraint(['transaction_id'], [u'transaction.id'], name=u'searchindexcursor_ibfk_1'),
                    sa.PrimaryKeyConstraint('id'),
                    mysql_default_charset=u'utf8mb4',
                    mysql_engine=u'InnoDB'
                    )
    op.drop_table('contactsearchindexcursor')
