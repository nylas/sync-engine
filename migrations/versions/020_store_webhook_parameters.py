"""store webhook parameters

Revision ID: 10ef1d46f016
Revises: 5a787816e2bc
Create Date: 2014-05-01 23:26:27.531705

"""

# revision identifiers, used by Alembic.
revision = '10ef1d46f016'
down_revision = '5a787816e2bc'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


def upgrade():
    op.create_table(
        'webhookparameters',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('public_id', mysql.BINARY(16), nullable=False),
        sa.Column('namespace_id', sa.Integer(), nullable=False),
        sa.Column('callback_url', sa.Text(), nullable=False),
        sa.Column('failure_notify_url', sa.Text(), nullable=True),
        sa.Column('to_addr', sa.String(length=255), nullable=True),
        sa.Column('from_addr', sa.String(length=255), nullable=True),
        sa.Column('cc_addr', sa.String(length=255), nullable=True),
        sa.Column('bcc_addr', sa.String(length=255), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('subject', sa.String(length=255), nullable=True),
        sa.Column('thread', mysql.BINARY(16), nullable=True),
        sa.Column('filename', sa.String(length=255), nullable=True),
        sa.Column('started_before', sa.DateTime(), nullable=True),
        sa.Column('started_after', sa.DateTime(), nullable=True),
        sa.Column('last_message_before', sa.DateTime(), nullable=True),
        sa.Column('last_message_after', sa.DateTime(), nullable=True),
        sa.Column('include_body', sa.Boolean(), nullable=False),
        sa.Column('max_retries', sa.Integer(), server_default='3',
                  nullable=False),
        sa.Column('retry_interval', sa.Integer(), server_default='60',
                  nullable=False),
        sa.Column('active', sa.Boolean(),
                  server_default=sa.sql.expression.true(),
                  nullable=False),
        sa.Column('min_processed_id', sa.Integer(), server_default='0',
                  nullable=False),
        sa.ForeignKeyConstraint(['namespace_id'], ['namespace.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_webhookparameters_public_id', 'webhookparameters',
                    ['public_id'], unique=False)


def downgrade():
    op.drop_index('ix_webhookparameters_public_id',
                  table_name='webhookparameters')
    op.drop_table('webhookparameters')
