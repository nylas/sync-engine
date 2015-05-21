"""update easuid schema 2

Revision ID: 3ee78a8b1ac6
Revises: 281b07fa75bb
Create Date: 2015-05-19 01:14:08.632291

"""

# revision identifiers, used by Alembic.
revision = '3ee78a8b1ac6'
down_revision = '281b07fa75bb'

import sqlalchemy as sa


def upgrade():
    from sqlalchemy.ext.declarative import declarative_base
    from inbox.models.session import session_scope
    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
    if not engine.has_table('easuid'):
        return
    Base = declarative_base()
    Base.metadata.reflect(engine)

    class EASUid(Base):
        __table__ = Base.metadata.tables['easuid']

    class EASFolderSyncStatus(Base):
        __table__ = Base.metadata.tables['easfoldersyncstatus']

    with session_scope(versioned=False) as db_session:
        max_easuid = db_session.query(sa.func.max(EASUid.id)).scalar()
        if max_easuid is None:
            return
        for i in range(0, max_easuid, 1000):
            results = db_session.query(EASUid, EASFolderSyncStatus). \
                join(EASFolderSyncStatus, sa.and_(
                    EASUid.fld_uid == EASFolderSyncStatus.eas_folder_id,
                    EASUid.device_id == EASFolderSyncStatus.device_id,
                    EASUid.easaccount_id == EASFolderSyncStatus.account_id)). \
                limit(1000).offset(i)
            for easuid, easfoldersyncstatus in results:
                easuid.easfoldersyncstatus_id = easfoldersyncstatus.id
            db_session.commit()


def downgrade():
    pass
