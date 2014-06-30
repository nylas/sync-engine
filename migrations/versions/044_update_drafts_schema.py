"""update drafts schema

Revision ID: 247cd689758c
Revises:5a136610b50b
Create Date: 2014-06-19 19:09:48.387937

"""

# revision identifiers, used by Alembic.
revision = '247cd689758c'
down_revision = '5a136610b50b'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


def upgrade():
    op.add_column('spoolmessage',
                  sa.Column('is_reply', sa.Boolean(),
                            server_default=sa.sql.expression.false(),
                            nullable=False))
    # Drop draft_copied_from and replyto_thread_id foreign key constraints.
    op.drop_constraint('spoolmessage_ibfk_4', 'spoolmessage',
                       type_='foreignkey')
    op.drop_constraint('spoolmessage_ibfk_5', 'spoolmessage',
                       type_='foreignkey')
    op.drop_column('spoolmessage', u'draft_copied_from')
    op.drop_column('spoolmessage', u'replyto_thread_id')
    op.drop_table(u'draftthread')


def downgrade():
    op.add_column('spoolmessage', sa.Column(u'replyto_thread_id',
                                            mysql.INTEGER(display_width=11),
                                            nullable=True))
    op.add_column('spoolmessage', sa.Column(u'draft_copied_from',
                                            mysql.INTEGER(display_width=11),
                                            nullable=True))
    op.drop_column('spoolmessage', 'is_reply')
    op.create_table(
        u'draftthread',
        sa.Column(u'created_at', mysql.DATETIME(), nullable=False),
        sa.Column(u'updated_at', mysql.DATETIME(), nullable=False),
        sa.Column(u'deleted_at', mysql.DATETIME(), nullable=True),
        sa.Column(u'public_id', sa.BINARY(length=16), nullable=False),
        sa.Column(u'id', mysql.INTEGER(display_width=11), nullable=False),
        sa.Column(u'master_public_id', sa.BINARY(length=16), nullable=False),
        sa.Column(u'thread_id', mysql.INTEGER(display_width=11),
                  autoincrement=False, nullable=False),
        sa.Column(u'message_id', mysql.INTEGER(display_width=11),
                  autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(['message_id'], [u'message.id'],
                                name=u'draftthread_ibfk_2'),
        sa.ForeignKeyConstraint(['thread_id'], [u'thread.id'],
                                name=u'draftthread_ibfk_1'),
        sa.PrimaryKeyConstraint(u'id'),
        mysql_default_charset=u'utf8mb4',
        mysql_engine=u'InnoDB'
    )
