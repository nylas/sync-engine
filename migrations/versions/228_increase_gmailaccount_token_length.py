"""increase gmailaccount token length

Revision ID: 3df39f4fbdec
Revises: 17b147c1d53c
Create Date: 2016-08-30 19:22:00.546553

"""

# revision identifiers, used by Alembic.
revision = '3df39f4fbdec'
down_revision = '17b147c1d53c'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.alter_column('gmailaccount', 'g_id_token', type_=sa.String(length=2048))
    op.alter_column('gmailauthcredentials', 'g_id_token', type_=sa.String(length=2048))
    pass


def downgrade():
    op.alter_column('gmailaccount', 'g_id_token', type_=sa.String(length=1024))
    op.alter_column('gmailauthcredentials', 'g_id_token', type_=sa.String(length=1024))
    pass
