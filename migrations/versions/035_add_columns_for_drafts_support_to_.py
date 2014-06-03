"""Add columns for drafts support to SpoolMessage

Revision ID: 24e085e152c0
Revises: 350a08df27ee
Create Date: 2014-05-13 22:50:03.938446

"""

# revision identifiers, used by Alembic.
revision = '24e085e152c0'
down_revision = '350a08df27ee'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


def upgrade():
    # Create DraftThread table
    op.create_table('draftthread',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('master_public_id', mysql.BINARY(16),
                              nullable=False),
                    sa.Column('thread_id', sa.Integer()),
                    sa.ForeignKeyConstraint(['thread_id'],
                                            ['thread.id'],
                                            ondelete='CASCADE'),
                    sa.Column('message_id', sa.Integer()),
                    sa.ForeignKeyConstraint(['message_id'],
                                            ['message.id'],
                                            ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id'),
                    sa.Column('created_at', sa.DateTime(),
                              nullable=False),
                    sa.Column('updated_at', sa.DateTime(),
                              nullable=False),
                    sa.Column('deleted_at', sa.DateTime(), nullable=True),
                    sa.Column('public_id', mysql.BINARY(16), nullable=False,
                              index=True),
                    )

    # Add columns to SpoolMessage table
    op.add_column('spoolmessage',
                  sa.Column('parent_draft_id', sa.Integer(), nullable=True))
    op.create_foreign_key('spoolmessage_ibfk_3',
                          'spoolmessage', 'spoolmessage',
                          ['parent_draft_id'], ['id'])

    op.add_column('spoolmessage',
                  sa.Column('draft_copied_from', sa.Integer(), nullable=True))
    op.create_foreign_key('spoolmessage_ibfk_4',
                          'spoolmessage', 'spoolmessage',
                          ['draft_copied_from'], ['id'])

    op.add_column('spoolmessage',
                  sa.Column('replyto_thread_id', sa.Integer(), nullable=True))
    op.create_foreign_key('spoolmessage_ibfk_5',
                          'spoolmessage', 'draftthread',
                          ['replyto_thread_id'], ['id'])

    op.add_column('spoolmessage', sa.Column('state', sa.Enum('draft',
                  'sending', 'sending failed', 'sent'), server_default='draft',
                  nullable=False))


def downgrade():
    op.drop_constraint('spoolmessage_ibfk_3', 'spoolmessage',
                       type_='foreignkey')
    op.drop_column('spoolmessage', 'parent_draft_id')

    op.drop_constraint('spoolmessage_ibfk_4', 'spoolmessage',
                       type_='foreignkey')
    op.drop_column('spoolmessage', 'draft_copied_from')

    op.drop_constraint('spoolmessage_ibfk_5', 'spoolmessage',
                       type_='foreignkey')
    op.drop_column('spoolmessage', 'replyto_thread_id')
    op.drop_column('spoolmessage', 'state')

    op.drop_table('draftthread')
