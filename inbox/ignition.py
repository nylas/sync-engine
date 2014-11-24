from sqlalchemy import create_engine

from inbox.sqlalchemy_ext.util import ForceStrictMode
from inbox.config import db_uri, config

DB_POOL_SIZE = config.get_required('DB_POOL_SIZE')
# Sane default of max overflow=5 if value missing in config.
DB_POOL_MAX_OVERFLOW = config.get('DB_POOL_MAX_OVERFLOW') or 5


def main_engine(pool_size=DB_POOL_SIZE, max_overflow=DB_POOL_MAX_OVERFLOW):
    engine = create_engine(db_uri(),
                           listeners=[ForceStrictMode()],
                           isolation_level='READ COMMITTED',
                           echo=False,
                           pool_size=pool_size,
                           pool_recycle=3600,
                           max_overflow=max_overflow,
                           connect_args={'charset': 'utf8mb4'})
    return engine


def init_db(engine):
    """
    Make the tables.

    This is called only from bin/create-db, which is run during setup.
    Previously we allowed this to run everytime on startup, which broke some
    alembic revisions by creating new tables before a migration was run.
    From now on, we should ony be creating tables+columns via SQLalchemy *once*
    and all subscequent changes done via migration scripts.

    """
    from inbox.models.base import MailSyncBase

    MailSyncBase.metadata.create_all(engine)
