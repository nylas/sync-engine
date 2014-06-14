from sqlalchemy import create_engine

from inbox.log import get_logger
log = get_logger()

from inbox.sqlalchemy_ext.util import ForceStrictMode

from inbox.config import db_uri

engine = create_engine(db_uri(),
                       listeners=[ForceStrictMode()],
                       isolation_level='READ COMMITTED',
                       echo=False,
                       pool_size=25,
                       max_overflow=10,
                       connect_args={'charset': 'utf8mb4'})


def init_db():
    """ Make the tables.

    This is called only from bin/create-db, which is run during setup.
    Previously we allowed this to run everytime on startup, which broke some
    alembic revisions by creating new tables before a migration was run.
    From now on, we should ony be creating tables+columns via SQLalchemy *once*
    and all subscequent changes done via migration scripts.
    """
    from inbox.models import register_backends
    table_mod_for = register_backends()

    from inbox.models.base import MailSyncBase

    MailSyncBase.metadata.create_all(engine)

    return table_mod_for
