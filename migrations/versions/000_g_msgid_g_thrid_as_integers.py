""" Store g_msgid and g_thrid as integers, not strings. For more efficiency.

Revision ID: 2605b23e1fe6
Revises: None
Create Date: 2014-03-04 00:34:31.817332

"""

# revision identifiers, used by Alembic.
revision = '2605b23e1fe6'
down_revision = None

from alembic import op
import sqlalchemy as sa

from sqlalchemy.dialects import mysql

def upgrade():
    op.alter_column('message', 'g_msgid', type_=mysql.BIGINT)
    op.alter_column('message', 'g_thrid', type_=mysql.BIGINT)

    op.create_index('ix_message_g_msgid', 'message', ['g_msgid'], unique=False)
    op.create_index('ix_message_g_thrid', 'message', ['g_thrid'], unique=False)

def downgrade():
    op.alter_column('message', 'g_msgid', type_=mysql.VARCHAR(40))
    op.alter_column('message', 'g_thrid', type_=mysql.VARCHAR(40))

    op.drop_index('ix_message_g_thrid', table_name='message')
    op.drop_index('ix_message_g_msgid', table_name='message')
