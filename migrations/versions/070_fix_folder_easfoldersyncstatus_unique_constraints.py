"""Fix Folder, EASFolderSyncStatus unique constraints

Revision ID: 2525c5245cc2
Revises: 479b3b84a73e
Create Date: 2014-07-28 18:57:24.476123

"""

# revision identifiers, used by Alembic.
revision = '2525c5245cc2'
down_revision = '479b3b84a73e'

from alembic import op
import sqlalchemy as sa


def upgrade():
    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)

    Base = sa.ext.declarative.declarative_base()
    Base.metadata.reflect(engine)

    op.drop_constraint('folder_fk1', 'folder', type_='foreignkey')
    op.drop_constraint('account_id', 'folder', type_='unique')

    op.create_foreign_key('folder_fk1',
                          'folder', 'account',
                          ['account_id'], ['id'])
    op.create_unique_constraint('account_id',
                                'folder',
                                ['account_id', 'name', 'canonical_name'])

    if 'easfoldersyncstatus' in Base.metadata.tables:
        op.create_unique_constraint('account_id_2',
                                    'easfoldersyncstatus',
                                    ['account_id', 'eas_folder_id'])


def downgrade():
    raise Exception('Unsupported, going back will break things.')
