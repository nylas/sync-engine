"""Cascade Folder deletes to EASUid

Revision ID: 2a748760ac63
Revises: 4af5952e8a5b
Create Date: 2014-07-19 00:28:08.258857

"""

# revision identifiers, used by Alembic.
revision = '2a748760ac63'
down_revision = '15dfc756a1b0'

from alembic import op

from inbox.ignition import engine
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
Base.metadata.reflect(engine)


def upgrade():
    if 'easfoldersyncstatus' in Base.metadata.tables:
        op.drop_constraint('easuid_ibfk_3', 'easuid', type_='foreignkey')
        op.create_foreign_key('easuid_ibfk_3', 'easuid', 'folder',
                              ['folder_id'], ['id'], ondelete='CASCADE')


def downgrade():
    op.drop_constraint('easuid_ibfk_3', 'easuid', type_='foreignkey')
    op.create_foreign_key('easuid_ibfk_3', 'easuid', 'folder',
                          ['folder_id'], ['id'])
