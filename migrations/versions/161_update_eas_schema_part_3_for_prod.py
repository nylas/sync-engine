"""update_eas_schema_part_3 for prod

Revision ID: 365071c47fa7
Revises: 182f2b40fa36
Create Date: 2015-05-04 19:06:03.595736

"""

# revision identifiers, used by Alembic.
revision = '365071c47fa7'
down_revision = '182f2b40fa36'

from alembic import op
from sqlalchemy.schema import MetaData


def upgrade():
    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)

    # Check affected tables present
    if not engine.has_table('easaccount'):
        return

    meta = MetaData()
    meta.reflect(bind=engine)
    easuid = meta.tables['easuid']

    # Check this migration hasn't run before
    if 'folder_id' not in [c.name for c in easuid.columns]:
        print 'This migration has been run, skipping.'
        return

    print 'Running migration'
    conn = op.get_bind()

    conn.execute('''ALTER TABLE easfoldersyncstatus
                    CHANGE name name varchar(191) NOT NULL''')
    conn.execute('''ALTER TABLE easuid DROP COLUMN folder_id''')
    conn.execute('''ALTER TABLE easfoldersyncstatus DROP COLUMN folder_id''')


def downgrade():
    pass
