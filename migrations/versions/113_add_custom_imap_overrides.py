"""Add custom IMAP overrides

Revision ID: 26bfb2e45c47
Revises:26911668870a
Create Date: 2014-10-17 01:41:47.989310

"""

# revision identifiers, used by Alembic.
revision = '26bfb2e45c47'
down_revision = '26911668870a'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('imapaccount', sa.Column('_imap_server_host',
                                           sa.String(length=255),
                                           nullable=True))
    op.add_column('imapaccount', sa.Column('_imap_server_port', sa.Integer(),
                                           server_default='993',
                                           nullable=False))
    op.add_column('imapaccount', sa.Column('_smtp_server_host',
                                           sa.String(length=255),
                                           nullable=True))
    op.add_column('imapaccount', sa.Column('_smtp_server_port', sa.Integer(),
                                           server_default='587',
                                           nullable=False))


def downgrade():
    op.drop_column('imapaccount', '_smtp_server_port')
    op.drop_column('imapaccount', '_smtp_server_host')
    op.drop_column('imapaccount', '_imap_server_port')
    op.drop_column('imapaccount', '_imap_server_host')
