"""Drafts as required folder

Revision ID: 41a7e825d108
Revises: 269247bc37d3
Create Date: 2014-03-13 21:14:25.652333

"""

# revision identifiers, used by Alembic.
revision = '41a7e825d108'
down_revision = '269247bc37d3'

from alembic import op
import sqlalchemy as sa



def upgrade():
    op.add_column('imapaccount', sa.Column('drafts_folder_name', sa.String(255), nullable=True))


def downgrade():
    op.drop_column('imapaccount', 'drafts_folder_name')
