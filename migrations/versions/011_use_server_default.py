"""Use server_default

Revision ID: 3237b6b1ee03
Revises: 193802835c33
Create Date: 2014-04-17 21:40:47.514728

"""

# revision identifiers, used by Alembic.
revision = '3237b6b1ee03'
down_revision = '3b511977a01f'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # Base tables
    op.alter_column('account', 'save_raw_messages',
                    server_default=sa.sql.expression.true(),
                    existing_type=sa.Boolean,
                    existing_server_default=sa.sql.expression.null(),
                    existing_nullable=None)
    op.alter_column('namespace', 'type',
                    server_default='root',
                    existing_type=sa.Enum('root', 'shared_folder'),
                    existing_server_default=sa.sql.expression.null(),
                    existing_nullable=False)
    op.alter_column('message', 'is_draft',
                    server_default=sa.sql.expression.false(),
                    existing_type=sa.Boolean,
                    existing_server_default=sa.sql.expression.null(),
                    existing_nullable=False)
    op.alter_column('message', 'decode_error',
                    server_default=sa.sql.expression.false(),
                    existing_type=sa.Boolean,
                    existing_server_default=sa.sql.expression.null(),
                    existing_nullable=False)
    op.alter_column('block', 'is_inboxapp_attachment',
                    server_default=sa.sql.expression.false(),
                    existing_type=sa.Boolean,
                    existing_server_default=sa.sql.expression.null(),
                    existing_nullable=None)

    # Imap tables
    op.alter_column('imapuid', 'is_draft',
                    server_default=sa.sql.expression.false(),
                    existing_type=sa.Boolean,
                    existing_server_default=sa.sql.expression.null(),
                    existing_nullable=False)
    op.alter_column('imapuid', 'is_seen',
                    server_default=sa.sql.expression.false(),
                    existing_type=sa.Boolean,
                    existing_server_default=sa.sql.expression.null(),
                    existing_nullable=False)
    op.alter_column('imapuid', 'is_flagged',
                    server_default=sa.sql.expression.false(),
                    existing_type=sa.Boolean,
                    existing_server_default=sa.sql.expression.null(),
                    existing_nullable=False)
    op.alter_column('imapuid', 'is_recent',
                    server_default=sa.sql.expression.false(),
                    existing_type=sa.Boolean,
                    existing_server_default=sa.sql.expression.null(),
                    existing_nullable=False)
    op.alter_column('imapuid', 'is_answered',
                    server_default=sa.sql.expression.false(),
                    existing_type=sa.Boolean,
                    existing_server_default=sa.sql.expression.null(),
                    existing_nullable=False)
    op.alter_column('foldersync', 'state',
                    server_default='initial',
                    existing_type=sa.Enum('initial', 'initial uidinvalid',
                        'poll', 'poll uidinvalid', 'finish'),
                    existing_server_default=sa.sql.expression.null(),
                    existing_nullable=False)

    # EAS tables
    op.alter_column('easaccount', 'eas_account_sync_key',
                    server_default='0',
                    nullable=False,
                    existing_type=sa.String(64),
                    existing_server_default=sa.sql.expression.null(),
                    existing_nullable=None)
    op.alter_column('easaccount', 'eas_state',
                    server_default='sync',
                    nullable=False,
                    existing_type=sa.Enum('sync', 'sync keyinvalid', 'finish'),
                    existing_server_default=sa.sql.expression.null(),
                    existing_nullable=None)
    op.alter_column('easuid', 'is_draft',
                    server_default=sa.sql.expression.false(),
                    existing_type=sa.Boolean,
                    existing_server_default=sa.sql.expression.null(),
                    existing_nullable=False)
    op.alter_column('easuid', 'is_flagged',
                    server_default=sa.sql.expression.false(),
                    existing_type=sa.Boolean,
                    existing_server_default=sa.sql.expression.null(),
                    existing_nullable=False)
    op.alter_column('easuid', 'is_seen',
                    server_default=sa.sql.expression.false(),
                    nullable=False,
                    existing_type=sa.Boolean,
                    existing_server_default=sa.sql.expression.null(),
                    existing_nullable=True)
    op.alter_column('easfoldersync', 'state',
                    server_default='initial',
                    existing_type=sa.Enum('initial', 'initial uidinvalid',
                        'poll', 'poll uidinvalid', 'finish'),
                    existing_server_default=sa.sql.expression.null(),
                    existing_nullable=False)
    op.alter_column('easfoldersync', 'eas_folder_sync_key',
                    nullable=False,
                    server_default='0',
                    existing_type=sa.String(64),
                    existing_server_default=sa.sql.expression.null(),
                    existing_nullable=None)


def downgrade():
    # Only downgrade those that can be nullable
    op.alter_column('account', 'save_raw_messages',
                    server_default=sa.sql.expression.null(),
                    existing_type=sa.Boolean,
                    existing_server_default=sa.sql.expression.true(),
                    existing_nullable=None)
    op.alter_column('block', 'is_inboxapp_attachment',
                    server_default=sa.sql.expression.null(),
                    existing_type=sa.Boolean,
                    existing_server_default=sa.sql.expression.false(),
                    existing_nullable=None)
