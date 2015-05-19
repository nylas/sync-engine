"""imap table cleanups

Revision ID: 29217fad3f46
Revises: 161b88c17615
Create Date: 2014-07-01 18:56:55.962529

"""

# revision identifiers, used by Alembic.
revision = '29217fad3f46'
down_revision = '1b751e8d9cac'

from alembic import op
import sqlalchemy as sa


def upgrade():
    from inbox.models.session import session_scope
    from inbox.models.folder import Folder
    from inbox.sqlalchemy_ext.util import JSON
    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)

    ### foldersync => imapfoldersyncstatus
    # note that renaming a table does in fact migrate constraints + indexes too
    op.rename_table('foldersync', 'imapfoldersyncstatus')

    op.alter_column('imapfoldersyncstatus', '_sync_status',
                    existing_type=JSON(), nullable=True,
                    new_column_name='_metrics')

    op.add_column('imapfoldersyncstatus',
                  sa.Column('folder_id', sa.Integer(), nullable=False))

    ### uidvalidity => imapfolderinfo
    op.rename_table('uidvalidity', 'imapfolderinfo')
    op.alter_column('imapfolderinfo', 'uid_validity',
                    existing_type=sa.Integer(), nullable=False,
                    new_column_name='uidvalidity')
    op.alter_column('imapfolderinfo', 'highestmodseq',
                    existing_type=sa.Integer(), nullable=True)

    op.drop_constraint('imapfolderinfo_ibfk_1',
                       'imapfolderinfo', type_='foreignkey')
    op.alter_column('imapfolderinfo', 'imapaccount_id',
                    existing_type=sa.Integer(), nullable=False,
                    new_column_name='account_id')
    op.create_foreign_key('imapfolderinfo_ibfk_1',
                          'imapfolderinfo', 'imapaccount',
                          ['account_id'], ['id'])

    op.add_column('imapfolderinfo',
                  sa.Column('folder_id', sa.Integer(), nullable=False))

    ### imapuid
    op.drop_constraint('imapuid_ibfk_1', 'imapuid', type_='foreignkey')
    op.alter_column('imapuid', 'imapaccount_id',
                    existing_type=sa.Integer(), nullable=False,
                    new_column_name='account_id')
    op.create_foreign_key('imapuid_ibfk_1',
                          'imapuid', 'imapaccount', ['account_id'], ['id'])

    ### migrate data and add new constraints
    Base = sa.ext.declarative.declarative_base()
    Base.metadata.reflect(engine)

    if 'easfoldersync' in Base.metadata.tables:
        op.rename_table('easfoldersync', 'easfoldersyncstatus')
        op.add_column('easfoldersyncstatus',
                      sa.Column('folder_id', sa.Integer(), nullable=False))
        op.alter_column('easfoldersyncstatus', '_sync_status',
                        existing_type=JSON(), nullable=True,
                        new_column_name='_metrics')
        Base.metadata.reflect(engine)

        class EASFolderSyncStatus(Base):
            __table__ = Base.metadata.tables['easfoldersyncstatus']

    class ImapFolderSyncStatus(Base):
        __table__ = Base.metadata.tables['imapfoldersyncstatus']

    class ImapFolderInfo(Base):
        __table__ = Base.metadata.tables['imapfolderinfo']

    with session_scope(versioned=False) \
            as db_session:
        folder_id_for = dict([((account_id, name.lower()), id_)
                              for id_, account_id, name in
                              db_session.query(Folder.id, Folder.account_id,
                                               Folder.name)])
        for status in db_session.query(ImapFolderSyncStatus):
            print "migrating", status.folder_name
            status.folder_id = folder_id_for[
                (status.account_id, status.folder_name.lower())]
        db_session.commit()
        if 'easfoldersyncstatus' in Base.metadata.tables:
            for status in db_session.query(EASFolderSyncStatus):
                print "migrating", status.folder_name
                folder_id = folder_id_for.get(
                    (status.account_id, status.folder_name.lower()))
                if folder_id is not None:
                    status.folder_id = folder_id
                else:
                    # EAS folder rows *may* not exist if have no messages
                    folder = Folder(account_id=status.account_id, name=status.folder_name)
                    db_session.add(folder)
                    db_session.commit()
                    status.folder_id = folder.id
            db_session.commit()
            # some weird alembic bug? need to drop and recreate this FK
            op.drop_constraint('easfoldersyncstatus_ibfk_1',
                               'easfoldersyncstatus', type_='foreignkey')
            op.drop_column('easfoldersyncstatus', 'folder_name')
            op.create_foreign_key('easfoldersyncstatus_ibfk_1',
                                  'easfoldersyncstatus',
                                  'easaccount', ['account_id'], ['id'])
            op.create_foreign_key('easfoldersyncstatus_ibfk_2',
                                  'easfoldersyncstatus', 'folder',
                                  ['folder_id'], ['id'])
            op.create_unique_constraint('account_id', 'easfoldersyncstatus',
                                        ['account_id', 'folder_id'])

    # some weird alembic bug? need to drop and recreate this FK
    op.drop_constraint('imapfoldersyncstatus_ibfk_1', 'imapfoldersyncstatus',
                       type_='foreignkey')
    op.drop_constraint('account_id', 'imapfoldersyncstatus', type_='unique')
    op.drop_column('imapfoldersyncstatus', 'folder_name')
    op.create_foreign_key('imapfoldersyncstatus_ibfk_1',
                          'imapfoldersyncstatus',
                          'imapaccount', ['account_id'], ['id'])
    op.create_foreign_key('imapfoldersyncstatus_ibfk_2',
                          'imapfoldersyncstatus', 'folder',
                          ['folder_id'], ['id'])
    op.create_unique_constraint('account_id', 'imapfoldersyncstatus',
                                ['account_id', 'folder_id'])

    with session_scope(versioned=False) \
            as db_session:
        for info in db_session.query(ImapFolderInfo):
            print "migrating", info.folder_name
            info.folder_id = folder_id_for[
                (info.account_id, info.folder_name.lower())]
        db_session.commit()

    # some weird alembic bug? need to drop and recreate this FK
    op.drop_constraint('imapfolderinfo_ibfk_1', 'imapfolderinfo',
                       type_='foreignkey')
    op.drop_constraint('imapaccount_id', 'imapfolderinfo', type_='unique')
    op.drop_column('imapfolderinfo', 'folder_name')
    op.create_foreign_key('imapfolderinfo_ibfk_1', 'imapfolderinfo',
                          'imapaccount', ['account_id'], ['id'])
    op.create_foreign_key('imapfolderinfo_ibfk_2', 'imapfolderinfo', 'folder',
                          ['folder_id'], ['id'])
    op.create_unique_constraint('imapaccount_id', 'imapfolderinfo',
                                ['account_id', 'folder_id'])


def downgrade():
    raise Exception("no going back!")
