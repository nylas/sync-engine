"""update_eas_schema_part_3

Revision ID: 4e6eedda36af
Revises: 5aa3f27457c
Create Date: 2015-04-06 23:35:00.178901

"""

# revision identifiers, used by Alembic.
revision = '4e6eedda36af'
down_revision = '5aa3f27457c'

from alembic import op


def upgrade():
    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
    # Do nothing if the affected table isn't present.
    if not engine.has_table('easaccount'):
        return

    conn = op.get_bind()
    conn.execute('''ALTER TABLE easfoldersyncstatus
                    CHANGE name name varchar(191) NOT NULL''')
    conn.execute('''ALTER TABLE easuid DROP COLUMN folder_id''')
    conn.execute('''ALTER TABLE easfoldersyncstatus DROP COLUMN folder_id''')


def downgrade():
    raise Exception()
