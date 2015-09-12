"""
Removes deleted_at constraint from easfoldersyncstatus and category

Revision ID: 583e083d4512
Revises: 420ccbea2c5e
Create Date: 2015-09-09 17:43:11.191169

"""

# revision identifiers, used by Alembic.
revision = '583e083d4512'
down_revision = '420ccbea2c5e'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
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


def downgrade():
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
