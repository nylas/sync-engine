"""tag API migration

Revision ID: 40629415951c
Revises: 924ffd092832
Create Date: 2014-05-13 03:20:41.488982

"""

# revision identifiers, used by Alembic.
revision = '40629415951c'
down_revision = '924ffd092832'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.ext.declarative import declarative_base
from contextlib import contextmanager
from datetime import datetime


def upgrade():
    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)

    Session = sessionmaker(bind=engine)

    @contextmanager
    def basic_session():
        # Using the InboxSession is kind of a pain in this migration, so let's
        # just roll with a normal sqlalchemy session.
        session = Session(autoflush=True, autocommit=False)
        try:
            yield session
            session.commit()
        except:
            session.rollback()
            raise
        finally:
            session.close()

    op.rename_table('internaltag', 'usertag')
    op.create_table(
        'usertagitem',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('thread_id', sa.Integer(), nullable=False),
        sa.Column('usertag_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['thread_id'], ['thread.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['usertag_id'], ['usertag.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.add_column(u'folder', sa.Column('exposed_name', sa.String(length=255),
                                       nullable=True))
    op.add_column(u'folder', sa.Column('public_id', sa.String(length=191),
                                       nullable=True))

    op.add_column(u'account', sa.Column('provider_prefix',
                                        sa.String(length=64),
                                        nullable=False))
    op.add_column(u'account', sa.Column('important_folder_id', sa.Integer,
                                        nullable=True))

    Base = declarative_base()
    Base.metadata.reflect(engine)

    class Folder(Base):
        __table__ = Base.metadata.tables['folder']
        account = relationship('Account', foreign_keys='Folder.account_id',
                               backref='folders')

    class FolderItem(Base):
        __table__ = Base.metadata.tables['folderitem']
        folder = relationship('Folder', backref='threads', lazy='joined')

    class Account(Base):
        __table__ = Base.metadata.tables['account']

    print "setting provider_prefix for current accounts"
    with basic_session() as db_session:
        for account in db_session.query(Account):
            if account.provider == 'gmail':
                account.provider_prefix = 'gmail'
            elif account.provider == 'eas':
                account.provider_prefix = 'exchange'
        db_session.commit()

        print "Merging folders"
        for name, alias in [('Sent', '[Gmail]/Sent Mail'),
                            ('Draft', '[Gmail]/Drafts'),
                            ('Starred', '[Gmail]/Starred'),
                            ('Important', '[Gmail]/Important')]:
            for account in db_session.query(Account):
                if account.provider != 'gmail':
                    continue

                src = db_session.query(Folder).filter(
                    Folder.account == account,
                    Folder.name == name).first()
                if src is None:
                    continue
                try:
                    dest = db_session.query(Folder).filter(
                        Folder.account == account,
                        Folder.name == alias).one()
                except NoResultFound:
                    # Create destination folder if it doesn't exist.
                    # (in particular, databases created before migration 024
                    # have a [Gmail]/Important folder, but databases created
                    # after may not).
                    dest = Folder(account=src.account,
                                  name=alias,
                                  created_at=datetime.utcnow(),
                                  updated_at=datetime.utcnow())
                    db_session.add(dest)

                for folderitem in db_session.query(FolderItem).filter(
                        FolderItem.folder == src).yield_per(500):
                    folderitem.folder = dest

                db_session.delete(src)

        db_session.commit()

    # Assuming we have only English Gmail accounts synced, we can cheat here.
    print "Adding public_id and exposed_name to folders."
    with basic_session() as db_session:
        for folder in db_session.query(Folder):
            if folder.account.provider != 'gmail':
                # punt on non-Gmail providers for now
                continue
            if folder.name == '[Gmail]/All Mail':
                folder.public_id = 'all'
                folder.exposed_name = 'all'
            elif folder.name == '[Gmail]/Drafts':
                folder.public_id = 'drafts'
                folder.exposed_name = 'drafts'
            elif folder.name == '[Gmail]/Sent Mail':
                folder.public_id = 'sent'
                folder.exposed_name = 'sent'
            elif folder.name == '[Gmail]/Starred':
                folder.public_id = 'starred'
                folder.exposed_name = 'starred'
            elif folder.name == '[Gmail]/Spam':
                folder.public_id = 'spam'
                folder.exposed_name = 'spam'
            elif folder.name == '[Gmail]/Trash':
                folder.public_id = 'trash'
                folder.exposed_name = 'trash'
            elif folder.name == '[Gmail]/Important':
                folder.public_id = 'important'
                folder.exposed_name = 'important'
            elif folder.name == 'Inbox':
                folder.public_id = 'inbox'
                folder.exposed_name = 'inbox'
            else:
                folder.exposed_name = '-'.join(('gmail', folder.name.lower()))

        db_session.commit()


def downgrade():
    raise Exception("Not supported.")
