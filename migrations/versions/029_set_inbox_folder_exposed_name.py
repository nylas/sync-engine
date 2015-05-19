"""set inbox folder exposed name

Revision ID: 52a9a976a2e0
Revises: 40629415951c
Create Date: 2014-05-15 22:57:47.913610

"""

# revision identifiers, used by Alembic.
revision = '52a9a976a2e0'
down_revision = '40629415951c'

from sqlalchemy.ext.declarative import declarative_base


def upgrade():
    from inbox.models.session import session_scope
    from inbox.ignition import main_engine
    engine = main_engine(pool_size=1, max_overflow=0)
    Base = declarative_base()
    Base.metadata.reflect(engine)

    class Folder(Base):
        __table__ = Base.metadata.tables['folder']

    with session_scope(versioned=False) as db_session:
        for folder in db_session.query(Folder).filter(
                Folder.name == 'Inbox'):
            folder.public_id = 'inbox'
            folder.exposed_name = 'inbox'
        db_session.commit()


def downgrade():
    pass
