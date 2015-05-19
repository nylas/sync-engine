"""Remove EASFolderSyncStatus + Folder rows for folders we never sync

Revision ID: 2a748760ac63
Revises: 4af5952e8a5b
Create Date: 2014-07-19 00:28:08.258857

"""

# revision identifiers, used by Alembic.
revision = 'bb4f204f192'
down_revision = '2a748760ac63'



def upgrade():
    if 'easfoldersyncstatus' in Base.metadata.tables:
        from inbox.ignition import main_engine
        engine = main_engine(pool_size=1, max_overflow=0)
        from inbox.models.session import session_scope
        from sqlalchemy.ext.declarative import declarative_base
        from sqlalchemy.orm.exc import NoResultFound
        Base = declarative_base()
        Base.metadata.reflect(engine)
        from inbox.models.backends.eas import EASFolderSyncStatus
        from inbox.models import Folder
        from inbox.util.eas.constants import SKIP_FOLDERS

        with session_scope(versioned=False) as \
                db_session:
            statuses = db_session.query(EASFolderSyncStatus).filter(
                EASFolderSyncStatus.eas_folder_type.in_(SKIP_FOLDERS)).all()
            for s in statuses:
                db_session.delete(s)
                db_session.delete(s.folder)

            try:
                for status in db_session.query(EASFolderSyncStatus)\
                        .join(Folder).filter(
                            Folder.name == 'RecipientInfo').all():
                    db_session.delete(status)
                    db_session.delete(status.folder)
            except NoResultFound:
                pass

            db_session.commit()


def downgrade():
    raise Exception('Nope, not needed.')
