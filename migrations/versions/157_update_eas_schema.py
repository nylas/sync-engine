"""update_eas_schema_part_1

Revision ID: 18064f5205dd
Revises: 3c7f059a68ba
Create Date: 2015-04-06 22:15:51.908303

"""

# revision identifiers, used by Alembic.
revision = '18064f5205dd'
down_revision = '3c7f059a68ba'

from alembic import op


def upgrade():
    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
    # Do nothing if the affected table isn't present.
    if not engine.has_table('easaccount'):
        return

    conn = op.get_bind()

    # Drop folder_id foreign key constraint from easfoldersyncstatus table
    folder_fks = conn.execute(
        '''SELECT constraint_name FROM information_schema.key_column_usage
           WHERE table_name='easfoldersyncstatus' AND
           referenced_table_name='folder'
           AND constraint_schema=DATABASE()''').fetchall()
    for folder_fk, in folder_fks:
        conn.execute(
            'ALTER TABLE easfoldersyncstatus DROP FOREIGN KEY {}'.format(
                folder_fk))

    # Drop folder_id foreign key constraint from easuid table
    folder_fks = conn.execute(
        '''SELECT constraint_name FROM information_schema.key_column_usage
           WHERE table_name='easuid' AND
           referenced_table_name='folder'
           AND constraint_schema=DATABASE()''').fetchall()
    for folder_fk, in folder_fks:
        conn.execute(
            'ALTER TABLE easuid DROP FOREIGN KEY {}'.format(
                folder_fk))

    # Add new index on easuid table
    conn.execute(
        '''ALTER TABLE easuid ADD UNIQUE INDEX easaccount_id
            (easaccount_id, device_id, fld_uid, msg_uid)''')

    # Drop deprecated indices
    conn.execute('''ALTER TABLE easuid DROP INDEX folder_id,
                    DROP INDEX easuid_easaccount_id_folder_id''')
    conn.execute(
        '''ALTER TABLE easfoldersyncstatus DROP INDEX account_id''')

    # Make folder_id columns nullable so that we don't have to populate them.
    conn.execute(
        '''ALTER TABLE easfoldersyncstatus CHANGE folder_id folder_id int(11)
           DEFAULT NULL''')
    conn.execute(
        '''ALTER TABLE easuid CHANGE folder_id folder_id int(11)
           DEFAULT NULL''')

    # Add references to folder syncs for canonical folders
    conn.execute(
        '''ALTER TABLE easdevice
           ADD COLUMN archive_foldersync_id int(11) DEFAULT NULL,
           ADD COLUMN inbox_foldersync_id int(11) DEFAULT NULL,
           ADD COLUMN sent_foldersync_id int(11) DEFAULT NULL,
           ADD COLUMN trash_foldersync_id int(11) DEFAULT NULL,
           ADD FOREIGN KEY archive_foldersync_ibfk (archive_foldersync_id)
               REFERENCES easfoldersyncstatus (id) ON DELETE SET NULL,
           ADD FOREIGN KEY inbox_foldersync_ibfk (inbox_foldersync_id)
               REFERENCES easfoldersyncstatus (id) ON DELETE SET NULL,
           ADD FOREIGN KEY sent_foldersync_ibfk (sent_foldersync_id)
               REFERENCES easfoldersyncstatus (id) ON DELETE SET NULL,
           ADD FOREIGN KEY trash_foldersync_ibfk (trash_foldersync_id)
               REFERENCES easfoldersyncstatus (id) ON DELETE SET NULL''')

    # Add name, canonical_name columns
    conn.execute(
        '''ALTER TABLE easfoldersyncstatus
            ADD COLUMN name varchar(191) DEFAULT NULL,
            ADD COLUMN canonical_name varchar(191) DEFAULT NULL''')

    # Set server-side default for deprecated is_draft column
    conn.execute(
        '''ALTER TABLE easuid CHANGE is_draft is_draft tinyint(1) default 0
           NOT NULL''')


def downgrade():
    raise Exception()
