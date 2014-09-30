"""add message.inbox_uid index

Revision ID: 569b9d365295
Revises: 4015edc83ba
Create Date: 2014-09-29 21:28:35.135135

"""

# revision identifiers, used by Alembic.
revision = '569b9d365295'
down_revision = '4015edc83ba'

from alembic import op


def upgrade():
    op.create_index('ix_message_inbox_uid', 'message', ['inbox_uid'],
                    unique=False)


def downgrade():
    op.drop_index('ix_message_inbox_uid', table_name='message')
