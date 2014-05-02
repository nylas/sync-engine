from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from urllib import quote_plus as urlquote
from contextlib import contextmanager

from inbox.server.config import config, is_prod
from inbox.server.log import get_logger
log = get_logger()

from inbox.sqlalchemy.revision import versioned_session
from inbox.sqlalchemy.util import Base, ForceStrictMode


def engine_uri(database=None):
    """ By default doesn't include the specific database. """

    config_prefix = 'RDS' if is_prod() else 'MYSQL'

    username = config.get('{0}_USER'.format(config_prefix), None)
    assert username, "Must have database username to connect!"

    password = config.get('{0}_PASSWORD'.format(config_prefix), None)
    assert password, "Must have database password to connect!"

    host = config.get('{0}_HOSTNAME'.format(config_prefix), None)
    assert host, "Must have database to connect!"

    port = config.get('{0}_PORT'.format(config_prefix), None)
    assert port, "Must have database port to connect!"

    uri_template = 'mysql://{username}:{password}@{host}:{port}/{database}?charset=utf8mb4'

    return uri_template.format(
        username=username,
        # http://stackoverflow.com/questions/15728290/sqlalchemy-valueerror-for-slash-in-password-for-create-engine (also applicable to '+' sign)
        password=urlquote(password),
        host=host,
        port=port,
        database=database if database else '')


def db_uri():
    config_prefix = 'RDS' if is_prod() else 'MYSQL'
    database = config.get('{0}_DATABASE'.format(config_prefix), None)
    assert database, "Must have database name to connect!"
    return engine_uri(database)

engine = create_engine(db_uri(),
                       listeners=[ForceStrictMode()],
                       isolation_level='READ COMMITTED',
                       echo=False,
                       pool_size=25,
                       max_overflow=10)


def init_db():
    """ Make the tables.

    This is called only from create_db.py, which is run during setup.
    Previously we allowed this to run everytime on startup, which broke some
    alembic revisions by creating new tables before a migration was run.
    From now on, we should ony be creating tables+columns via SQLalchemy *once*
    and all subscequent changes done via migration scripts.
    """
    from inbox.server.models.tables.base import register_backends
    table_mod_for = register_backends()

    Base.metadata.create_all(engine)

    return table_mod_for

Session = sessionmaker(bind=engine)


def new_db_session(versioned=True):
    """ Create a new session.

    Most of the time you should be using session_scope() instead, since it
    handles cleanup properly. Sometimes you still need to use this function
    directly because of how context managers require all code using the
    created variable to be in a block; test setup is one example.

    Parameters
    ----------
    versioned : bool
        Do you want to enable the transaction log? (Almost always yes!)

    Returns
    -------
    sqlalchemy.orm.session.Session
        The created session.
    """
    from inbox.server.models.tables.base import Transaction, HasRevisions

    sess = Session(autoflush=True, autocommit=False)

    if versioned:
        return versioned_session(sess, Transaction, HasRevisions)
    else:
        return sess


@contextmanager
def session_scope(versioned=True):
    """ Provide a transactional scope around a series of operations.

    Takes care of rolling back failed transactions and closing the session
    when it goes out of scope.

    Note that sqlalchemy automatically starts a new database transaction when
    the session is created, and restarts a new transaction after every commit()
    on the session. Your database backend's transaction semantics are important
    here when reasoning about concurrency.

    Parameters
    ----------
    versioned : bool
        Do you want to enable the transaction log? (Almost always yes!)

    Yields
    ------
    sqlalchemy.orm.session.Session
        The created session.
    """
    session = new_db_session(versioned)
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()
