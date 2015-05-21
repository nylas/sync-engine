"""update_easuid_schema_4

Revision ID: d0427f9f3d1
Revises: 584356bf23a3
Create Date: 2015-05-19 21:35:03.342221

"""

# revision identifiers, used by Alembic.
revision = 'd0427f9f3d1'
down_revision = '584356bf23a3'

from alembic import op


def upgrade():
    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
    if not engine.has_table('easuid'):
        return

    conn = op.get_bind()
    conn.execute('''ALTER TABLE easuid
        CHANGE COLUMN msg_uid msg_uid INT(11) DEFAULT NULL,
        CHANGE COLUMN fld_uid fld_uid INT(11) DEFAULT NULL,
        ADD UNIQUE INDEX easaccount_id_2 (easaccount_id, device_id, easfoldersyncstatus_id, server_id)''')


def downgrade():
    raise Exception()
