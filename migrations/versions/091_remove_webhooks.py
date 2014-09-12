"""remove webhooks

Revision ID: 4b07b67498e1
Revises: 2b89164aa9cd
Create Date: 2014-09-12 21:15:06.890202

"""

# revision identifiers, used by Alembic.
revision = '4b07b67498e1'
down_revision = '2b89164aa9cd'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


def upgrade():
    op.drop_table('webhook')
    op.drop_table('lens')


def downgrade():
    op.create_table(
        'lens',
        sa.Column('public_id', sa.BINARY(length=16), nullable=False),
        sa.Column('created_at', mysql.DATETIME(), nullable=False),
        sa.Column('updated_at', mysql.DATETIME(), nullable=False),
        sa.Column('deleted_at', mysql.DATETIME(), nullable=True),
        sa.Column('id', mysql.INTEGER(display_width=11), nullable=False),
        sa.Column('namespace_id', mysql.INTEGER(display_width=11),
                  autoincrement=False, nullable=False),
        sa.Column('subject', mysql.VARCHAR(length=255), nullable=True),
        sa.Column('thread_public_id', sa.BINARY(length=16), nullable=True),
        sa.Column('started_before', mysql.DATETIME(), nullable=True),
        sa.Column('started_after', mysql.DATETIME(), nullable=True),
        sa.Column('last_message_before', mysql.DATETIME(), nullable=True),
        sa.Column('last_message_after', mysql.DATETIME(), nullable=True),
        sa.Column('any_email', mysql.VARCHAR(length=255), nullable=True),
        sa.Column('to_addr', mysql.VARCHAR(length=255), nullable=True),
        sa.Column('from_addr', mysql.VARCHAR(length=255), nullable=True),
        sa.Column('cc_addr', mysql.VARCHAR(length=255), nullable=True),
        sa.Column('bcc_addr', mysql.VARCHAR(length=255), nullable=True),
        sa.Column('filename', mysql.VARCHAR(length=255), nullable=True),
        sa.Column('tag', mysql.VARCHAR(length=255), nullable=True),
        sa.ForeignKeyConstraint(['namespace_id'], [u'namespace.id'],
                                name=u'lens_ibfk_1', ondelete=u'CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        mysql_default_charset=u'utf8mb4',
        mysql_engine=u'InnoDB'
    )
    op.create_table(
        'webhook',
        sa.Column('public_id', sa.BINARY(length=16), nullable=False),
        sa.Column('created_at', mysql.DATETIME(), nullable=False),
        sa.Column('updated_at', mysql.DATETIME(), nullable=False),
        sa.Column('deleted_at', mysql.DATETIME(), nullable=True),
        sa.Column('id', mysql.INTEGER(display_width=11), nullable=False),
        sa.Column('namespace_id', mysql.INTEGER(display_width=11),
                  autoincrement=False, nullable=False),
        sa.Column('lens_id', mysql.INTEGER(display_width=11),
                  autoincrement=False, nullable=False),
        sa.Column('callback_url', mysql.TEXT(), nullable=False),
        sa.Column('failure_notify_url', mysql.TEXT(), nullable=True),
        sa.Column('include_body', mysql.TINYINT(display_width=1),
                  autoincrement=False, nullable=False),
        sa.Column('max_retries', mysql.INTEGER(display_width=11),
                  server_default='3', autoincrement=False, nullable=False),
        sa.Column('retry_interval', mysql.INTEGER(display_width=11),
                  server_default='60', autoincrement=False, nullable=False),
        sa.Column('active', mysql.TINYINT(display_width=1), server_default='1',
                  autoincrement=False, nullable=False),
        sa.Column('min_processed_id', mysql.INTEGER(display_width=11),
                  server_default='0', autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(['lens_id'], [u'lens.id'],
                                name=u'webhook_ibfk_2', ondelete=u'CASCADE'),
        sa.ForeignKeyConstraint(['namespace_id'], [u'namespace.id'],
                                name=u'webhook_ibfk_1', ondelete=u'CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        mysql_default_charset=u'utf8mb4',
        mysql_engine=u'InnoDB'
    )
