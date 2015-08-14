"""save_imap_uidnext

Revision ID: 3583211a4838
Revises: 301d22aa96b8
Create Date: 2015-08-13 22:24:35.385260

"""

# revision identifiers, used by Alembic.
revision = '3583211a4838'
down_revision = '301d22aa96b8'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('imapfolderinfo', sa.Column('uidnext', sa.Integer(),
                                              nullable=True))


def downgrade():
    op.drop_column('imapfolderinfo', 'uidnext')
