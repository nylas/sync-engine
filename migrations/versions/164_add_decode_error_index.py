"""add message.decode_error index """

revision = '17dcbd7754e0'
down_revision = '457164360472'

from alembic import op


def upgrade():
    op.create_index('ix_message_decode_error', 'message',
                    ['decode_error'], unique=False)


def downgrade():
    op.drop_index('ix_message_decode_error', table_name='message')
