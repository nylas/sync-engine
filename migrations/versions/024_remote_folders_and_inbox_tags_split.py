"""more folder names, separate remote folders and inbox tags

Revision ID: 4c1eb89f6bed
Revises: 4c529b9bc68d
Create Date: 2014-05-01 02:20:00.936927

"""

# revision identifiers, used by Alembic.
revision = '4c1eb89f6bed'
down_revision = '4e04f752b7ad'

from alembic import op
import sqlalchemy as sa

from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.declarative import declarative_base

from sqlalchemy.dialects import mysql

CHUNK_SIZE = 250

# This is a bit of a hack (english locale only), but good enough for now.
folder_name_subst_map = {'archive': u'[Gmail]/All Mail',
                         'drafts': u'[Gmail]/Drafts',
                         'draft': u'[Gmail]/Drafts',
                         'important': u'[Gmail]/Important',
                         'inbox': u'Inbox',
                         'INBOX': u'Inbox',
                         'sent': u'[Gmail]/Sent Mail',
                         'spam': u'[Gmail]/Spam',
                         'starred': u'[Gmail]/Starred',
                         'trash': u'[Gmail]/Trash'}


def upgrade():
    easupdate = False

    print 'Creating new tables and columns...'
    op.create_table('folder',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('account_id', sa.Integer(), nullable=False),
                    sa.Column('name', sa.String(
                        length=191, collation='utf8mb4_general_ci'),
                        nullable=True),
                    sa.ForeignKeyConstraint(['account_id'], ['account.id'],
                                            ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('account_id', 'name')
                    )
    op.create_table('internaltag',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('public_id', mysql.BINARY(16), nullable=False),
                    sa.Column('namespace_id', sa.Integer(), nullable=False),
                    sa.Column('name', sa.String(length=191), nullable=False),
                    sa.Column('thread_id', sa.Integer(), nullable=False),
                    sa.ForeignKeyConstraint(['namespace_id'], ['namespace.id'],
                                            ondelete='CASCADE'),
                    sa.ForeignKeyConstraint(['thread_id'], ['thread.id'],
                                            ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('namespace_id', 'name')
                    )
    op.add_column('folderitem',
                  sa.Column('folder_id', sa.Integer(), nullable=True))
    op.create_foreign_key("fk_folder_id", "folderitem",
                          "folder", ["folder_id"], ["id"],
                          ondelete='CASCADE')

    op.add_column('account', sa.Column('inbox_folder_id',
                                       sa.Integer, nullable=True))
    op.add_column('account', sa.Column('sent_folder_id',
                                       sa.Integer, nullable=True))
    op.add_column('account', sa.Column('drafts_folder_id',
                                       sa.Integer, nullable=True))
    op.add_column('account', sa.Column('spam_folder_id',
                                       sa.Integer, nullable=True))
    op.add_column('account', sa.Column('trash_folder_id',
                                       sa.Integer, nullable=True))
    op.add_column('account', sa.Column('archive_folder_id',
                                       sa.Integer, nullable=True))
    op.add_column('account', sa.Column('all_folder_id',
                                       sa.Integer, nullable=True))
    op.add_column('account', sa.Column('starred_folder_id',
                                       sa.Integer, nullable=True))
    op.create_foreign_key('account_ibfk_2', 'account', 'folder',
                          ['inbox_folder_id'], ['id'])
    op.create_foreign_key('account_ibfk_3', 'account', 'folder',
                          ['sent_folder_id'], ['id'])
    op.create_foreign_key('account_ibfk_4', 'account', 'folder',
                          ['drafts_folder_id'], ['id'])
    op.create_foreign_key('account_ibfk_5', 'account', 'folder',
                          ['spam_folder_id'], ['id'])
    op.create_foreign_key('account_ibfk_6', 'account', 'folder',
                          ['trash_folder_id'], ['id'])
    op.create_foreign_key('account_ibfk_7', 'account', 'folder',
                          ['archive_folder_id'], ['id'])
    op.create_foreign_key('account_ibfk_8', 'account', 'folder',
                          ['all_folder_id'], ['id'])
    op.create_foreign_key('account_ibfk_9', 'account', 'folder',
                          ['starred_folder_id'], ['id'])

    op.add_column('imapuid', sa.Column('folder_id', sa.Integer, nullable=True))
    op.create_foreign_key('imapuid_ibfk_3', 'imapuid', 'folder',
                          ['folder_id'], ['id'])

    from inbox.models.session import session_scope
    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)

    Base = declarative_base()
    Base.metadata.reflect(engine)

    if 'easuid' in Base.metadata.tables:
        easupdate = True
        print 'Adding new EASUid columns...'

        op.add_column('easuid',
                      sa.Column('fld_uid', sa.Integer(), nullable=True))

        op.add_column('easuid',
                      sa.Column('folder_id', sa.Integer(), nullable=True))

        op.create_foreign_key('easuid_ibfk_3', 'easuid', 'folder',
                              ['folder_id'], ['id'])

        op.create_unique_constraint(
            'uq_easuid_folder_id_msg_uid_easaccount_id',
            'easuid',
            ['folder_id', 'msg_uid', 'easaccount_id'])

        op.create_index('easuid_easaccount_id_folder_id', 'easuid',
                        ['easaccount_id', 'folder_id'])

    # Include our changes to the EASUid table:
    Base = declarative_base()
    Base.metadata.reflect(engine)

    class Folder(Base):
        __table__ = Base.metadata.tables['folder']
        account = relationship('Account', foreign_keys='Folder.account_id',
                               backref='folders')

    class FolderItem(Base):
        __table__ = Base.metadata.tables['folderitem']
        folder = relationship('Folder', backref='threads', lazy='joined')

    class Thread(Base):
        __table__ = Base.metadata.tables['thread']
        folderitems = relationship('FolderItem', backref="thread",
                                   single_parent=True,
                                   cascade='all, delete, delete-orphan')
        namespace = relationship('Namespace', backref='threads')

    class Namespace(Base):
        __table__ = Base.metadata.tables['namespace']
        account = relationship('Account',
                               backref=backref('namespace', uselist=False))

    class Account(Base):
        __table__ = Base.metadata.tables['account']
        inbox_folder = relationship('Folder',
                                    foreign_keys='Account.inbox_folder_id')
        sent_folder = relationship('Folder',
                                   foreign_keys='Account.sent_folder_id')
        drafts_folder = relationship('Folder',
                                     foreign_keys='Account.drafts_folder_id')
        spam_folder = relationship('Folder',
                                   foreign_keys='Account.spam_folder_id')
        trash_folder = relationship('Folder',
                                    foreign_keys='Account.trash_folder_id')
        starred_folder = relationship('Folder',
                                      foreign_keys='Account.starred_folder_id')
        archive_folder = relationship('Folder',
                                      foreign_keys='Account.archive_folder_id')
        all_folder = relationship('Folder',
                                  foreign_keys='Account.all_folder_id')

    class ImapUid(Base):
        __table__ = Base.metadata.tables['imapuid']
        folder = relationship('Folder', backref='imapuids', lazy='joined')

    if easupdate:
        class EASUid(Base):
            __table__ = Base.metadata.tables['easuid']
            folder = relationship('Folder', foreign_keys='EASUid.folder_id',
                                  backref='easuids', lazy='joined')

    print 'Creating Folder rows and migrating FolderItems...'
    # not many folders per account, so shouldn't grow that big
    with session_scope(versioned=False) as db_session:
        folders = dict([((i.account_id, i.name), i)
                        for i in db_session.query(Folder).all()])
        count = 0
        for folderitem in db_session.query(FolderItem).join(Thread).join(
                Namespace).yield_per(CHUNK_SIZE):
            account_id = folderitem.thread.namespace.account_id
            if folderitem.thread.namespace.account.provider == 'gmail':
                if folderitem.folder_name in folder_name_subst_map:
                    new_folder_name = folder_name_subst_map[
                        folderitem.folder_name]
                else:
                    new_folder_name = folderitem.folder_name
            elif folderitem.thread.namespace.account.provider == 'eas':
                new_folder_name = folderitem.folder_name.title()

            if (account_id, new_folder_name) in folders:
                f = folders[(account_id, new_folder_name)]
            else:
                f = Folder(account_id=account_id,
                           name=new_folder_name)
                folders[(account_id, new_folder_name)] = f
            folderitem.folder = f
            count += 1
            if count > CHUNK_SIZE:
                db_session.commit()
                count = 0
        db_session.commit()

        print 'Migrating ImapUids to reference Folder rows...'
        for imapuid in db_session.query(ImapUid).yield_per(CHUNK_SIZE):
            account_id = imapuid.imapaccount_id
            if imapuid.folder_name in folder_name_subst_map:
                new_folder_name = folder_name_subst_map[imapuid.folder_name]
            else:
                new_folder_name = imapuid.folder_name
            if (account_id, new_folder_name) in folders:
                f = folders[(account_id, new_folder_name)]
            else:
                f = Folder(account_id=account_id,
                           name=new_folder_name)
                folders[(account_id, new_folder_name)] = f
            imapuid.folder = f
            count += 1
            if count > CHUNK_SIZE:
                db_session.commit()
                count = 0
        db_session.commit()

        if easupdate:
            print 'Migrating EASUids to reference Folder rows...'

            for easuid in db_session.query(EASUid).yield_per(CHUNK_SIZE):
                account_id = easuid.easaccount_id
                new_folder_name = easuid.folder_name

                if (account_id, new_folder_name) in folders:
                    f = folders[(account_id, new_folder_name)]
                else:
                    f = Folder(account_id=account_id,
                               name=new_folder_name)
                    folders[(account_id, new_folder_name)] = f
                easuid.folder = f
                count += 1
                if count > CHUNK_SIZE:
                    db_session.commit()
                    count = 0
            db_session.commit()

        print 'Migrating *_folder_name fields to reference Folder rows...'
        for account in db_session.query(Account).filter_by(provider='gmail'):
            if account.inbox_folder_name:
                # hard replace INBOX with canonicalized caps
                k = (account.id, 'Inbox')
                if k in folders:
                    account.inbox_folder = folders[k]
                else:
                    account.inbox_folder = Folder(
                        account_id=account.id,
                        name=folder_name_subst_map[account.inbox_folder_name])
            if account.sent_folder_name:
                k = (account.id, account.sent_folder_name)
                if k in folders:
                    account.sent_folder = folders[k]
                else:
                    account.sent_folder = Folder(
                        account_id=account.id,
                        name=account.sent_folder_name)
            if account.drafts_folder_name:
                k = (account.id, account.drafts_folder_name)
                if k in folders:
                    account.drafts_folder = folders[k]
                else:
                    account.drafts_folder = Folder(
                        account_id=account.id,
                        name=account.drafts_folder_name)
            # all/archive mismatch is intentional; semantics have changed
            if account.archive_folder_name:
                k = (account.id, account.archive_folder_name)
                if k in folders:
                    account.all_folder = folders[k]
                else:
                    account.all_folder = Folder(
                        account_id=account.id,
                        name=account.archive_folder_name)
        db_session.commit()

        if easupdate:
            print "Migrating EAS accounts' *_folder_name fields to reference "\
                  "Folder rows..."

            for account in db_session.query(Account).filter_by(provider='eas'):
                if account.inbox_folder_name:
                    k = (account.id, account.inbox_folder_name)
                    if k in folders:
                        account.inbox_folder = folders[k]
                    else:
                        account.inbox_folder = Folder(
                            account_id=account.id,
                            name=account.inbox_folder_name)
                if account.sent_folder_name:
                    k = (account.id, account.sent_folder_name)
                    if k in folders:
                        account.sent_folder = folders[k]
                    else:
                        account.sent_folder = Folder(
                            account_id=account.id,
                            name=account.sent_folder_name)
                if account.drafts_folder_name:
                    k = (account.id, account.drafts_folder_name)
                    if k in folders:
                        account.drafts_folder = folders[k]
                    else:
                        account.drafts_folder = Folder(
                            account_id=account.id,
                            name=account.drafts_folder_name)
                if account.archive_folder_name:
                    k = (account.id, account.archive_folder_name)
                    if k in folders:
                        account.archive_folder = folders[k]
                    else:
                        account.archive_folder = Folder(
                            account_id=account.id,
                            name=account.archive_folder_name)
            db_session.commit()

    print 'Final schema tweaks and new constraint enforcement'
    op.alter_column('folderitem', 'folder_id', existing_type=sa.Integer(),
                    nullable=False)
    op.drop_constraint('folder_name', 'folderitem', type_='unique')
    op.drop_constraint('folder_name', 'imapuid', type_='unique')
    op.create_unique_constraint('uq_imapuid_folder_id_msg_uid_imapaccount_id',
                                'imapuid',
                                ['folder_id', 'msg_uid', 'imapaccount_id'])
    op.drop_column('folderitem', 'folder_name')
    op.drop_column('imapuid', 'folder_name')
    op.drop_column('account', 'inbox_folder_name')
    op.drop_column('account', 'drafts_folder_name')
    op.drop_column('account', 'sent_folder_name')
    op.drop_column('account', 'archive_folder_name')

    if easupdate:
        print 'Dropping old EASUid columns...'

        op.drop_constraint('folder_name', 'easuid', type_='unique')
        op.drop_index('easuid_easaccount_id_folder_name', 'easuid')
        op.drop_column('easuid', 'folder_name')


def downgrade():
    raise Exception("Not supported, will lose data!")
