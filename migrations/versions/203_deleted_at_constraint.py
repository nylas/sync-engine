"""Add deleted_at constraint to EASFolderSyncStatus, Label, Folder, and Category

Revision ID: 420ccbea2c5e
Revises: 2e515548043b
Create Date: 2015-09-01 18:09:11.955599

"""

# revision identifiers, used by Alembic.
revision = '420ccbea2c5e'
down_revision = '2e515548043b'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("set @@foreign_key_checks = 0;"))
    op.drop_constraint(u'namespace_id', 'category', type_='unique')
    op.create_unique_constraint(u'namespace_id', 'category',
                                ['namespace_id', 'name', 'display_name',
                                 'deleted_at'])

    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
    if not engine.has_table('easfoldersyncstatus'):
        return
    op.drop_constraint(u'account_id_2', 'easfoldersyncstatus', type_='unique')
    op.create_unique_constraint(u'account_id_2', 'easfoldersyncstatus',
                                ['account_id', 'device_id', 'eas_folder_id',
                                 'deleted_at'])
    conn.execute(text("set @@foreign_key_checks = 1;"))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("set @@foreign_key_checks = 0;"))
    op.drop_constraint(u'namespace_id', 'category', type_='unique')
    op.create_unique_constraint(u'namespace_id', 'category',
                                ['namespace_id', 'name', 'display_name'])

    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
    if not engine.has_table('easfoldersyncstatus'):
        return
    op.drop_constraint(u'account_id_2', 'easfoldersyncstatus', type_='unique')
    op.create_unique_constraint(u'account_id_2', 'easfoldersyncstatus',
                                ['account_id', 'device_id', 'eas_folder_id'])
    conn.execute(text("set @@foreign_key_checks = 1;"))
