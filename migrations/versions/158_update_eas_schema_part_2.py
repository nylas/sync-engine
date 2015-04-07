"""update_eas_schema_part_2

Revision ID: 5aa3f27457c
Revises: 18064f5205dd
Create Date: 2015-04-06 23:22:23.038022

"""

# revision identifiers, used by Alembic.
revision = '5aa3f27457c'
down_revision = '18064f5205dd'

from alembic import op


def upgrade():
    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
    # Do nothing if the affected table isn't present.
    if not engine.has_table('easaccount'):
        return

    conn = op.get_bind()
    # Populate new easfoldersyncstatus columns. This should be run offline
    # (stop-the-world).
    conn.execute(
        '''UPDATE easfoldersyncstatus JOIN folder ON
            easfoldersyncstatus.folder_id=folder.id SET
            easfoldersyncstatus.name=folder.name,
            easfoldersyncstatus.canonical_name=folder.canonical_name''')

    # Populate references to canonical foldersyncs.
    conn.execute(
        '''UPDATE easdevice JOIN easfoldersyncstatus ON
            easdevice.id=easfoldersyncstatus.device_id AND
            easfoldersyncstatus.eas_folder_type='2'
            SET easdevice.inbox_foldersync_id=easfoldersyncstatus.id''')
    conn.execute(
        '''UPDATE easdevice JOIN easfoldersyncstatus ON
            easdevice.id=easfoldersyncstatus.device_id AND
            easfoldersyncstatus.eas_folder_type='4'
            SET easdevice.trash_foldersync_id=easfoldersyncstatus.id''')
    conn.execute(
        '''UPDATE easdevice JOIN easfoldersyncstatus ON
            easdevice.id=easfoldersyncstatus.device_id AND
            easfoldersyncstatus.eas_folder_type='5'
            SET easdevice.sent_foldersync_id=easfoldersyncstatus.id''')
    conn.execute(
        '''UPDATE easdevice JOIN easfoldersyncstatus ON
            easdevice.id=easfoldersyncstatus.device_id AND
            easfoldersyncstatus.canonical_name='archive'
            SET easdevice.archive_foldersync_id=easfoldersyncstatus.id''')


def downgrade():
    raise Exception()
