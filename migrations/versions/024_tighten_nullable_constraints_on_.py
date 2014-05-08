"""Tighten nullable constraints on ImapUids.

Will help prevent future heisenbugs.


Revision ID: 4e04f752b7ad
Revises: 4c1eb89f6bed
Create Date: 2014-05-08 19:26:07.253333

"""

# revision identifiers, used by Alembic.
revision = '4e04f752b7ad'
down_revision = '4c1eb89f6bed'

from alembic import op


def upgrade():
    op.alter_column('imapuid', 'message_id', nullable=False)
    # unrelated to current bugs, but no reason this should be NULLable either
    op.alter_column('imapuid', 'msg_uid', nullable=False)


def downgrade():
    op.alter_column('imapuid', 'message_id', nullable=True)
    op.alter_column('imapuid', 'msg_uid', nullable=True)
