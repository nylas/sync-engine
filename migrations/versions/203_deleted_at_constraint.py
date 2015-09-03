"""Add deleted_at constraint to EASFolderSyncStatus, Label, Folder, and Category

Revision ID: 420ccbea2c5e
Revises: 2e515548043b
Create Date: 2015-09-01 18:09:11.955599

"""

# revision identifiers, used by Alembic.
revision = '420ccbea2c5e'
down_revision = '2e515548043b'

from alembic import op


def upgrade():
    op.create_unique_constraint(u'namespace_id_3', 'category',
                                ['namespace_id', 'name', 'display_name',
                                 'deleted_at'])
    op.drop_constraint(u'namespace_id', 'category', type_='unique')
    op.create_unique_constraint(u'account_id_2', 'folder',
                                 ['account_id', 'name', 'deleted_at'])
    op.drop_constraint(u'account_id', 'folder', type_='unique')
    op.create_unique_constraint(u'account_id_2', 'label',
                                ['account_id', 'name', 'canonical_name',
                                 'deleted_at'])
    op.drop_constraint(u'account_id', 'label', type_='unique')

    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
    if not engine.has_table('easfoldersyncstatus'):
        return
    op.create_unique_constraint(u'account_id_2', 'easfoldersyncstatus',
                                ['account_id', 'device_id', 'eas_folder_id',
                                 'deleted_at'])
    op.drop_constraint(u'account_id', 'easfoldersyncstatus', type_='unique')


def downgrade():
    op.create_unique_constraint(u'account_id', 'label',
                                ['account_id', 'name', 'canonical_name'])
    op.drop_constraint(u'account_id_2', 'label', type_='unique')
    op.create_unique_constraint(u'account_id', 'folder',
                                ['account_id', 'name'])
    op.drop_constraint(u'account_id_2', 'folder', type_='unique')
    op.create_unique_constraint(u'namespace_id', 'category',
                                ['namespace_id', 'name', 'display_name'])
    op.drop_constraint(u'namespace_id_3', 'category', type_='unique')

    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
    if not engine.has_table('easfoldersyncstatus'):
        return
    op.create_unique_constraint(u'account_id', 'easfoldersyncstatus',
                                ['account_id', 'device_id', 'eas_folder_id'])
    op.drop_constraint(u'account_id_2', 'easfoldersyncstatus', type_='unique')

