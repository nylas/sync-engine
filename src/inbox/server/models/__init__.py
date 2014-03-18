from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from urllib import quote_plus as urlquote
from contextlib import contextmanager

from inbox.server.config import config, is_prod
from inbox.server.log import get_logger
log = get_logger()

from inbox.sqlalchemy.revision import versioned_session
from inbox.sqlalchemy.util import Base, ForceStrictMode


def db_uri():

    config_prefix = 'RDS' if is_prod() else 'MYSQL'

    username = config.get('{0}_USER'.format(config_prefix), None)
    assert username, "Must have database username to connect!"

    password = config.get('{0}_PASSWORD'.format(config_prefix), None)
    assert password, "Must have database password to connect!"

    host = config.get('{0}_HOSTNAME'.format(config_prefix), None)
    assert host, "Must have database to connect!"

    port = config.get('{0}_PORT'.format(config_prefix), None)
    assert port, "Must have database port to connect!"

    database = config.get('{0}_DATABASE'.format(config_prefix), None)
    assert host, "Must have database name to connect!"

    uri_template = 'mysql://{username}:{password}@{host}:{port}/{database}?charset=utf8mb4'

    return uri_template.format(
        username=username,
        # http://stackoverflow.com/questions/15728290/sqlalchemy-valueerror-for-slash-in-password-for-create-engine (also applicable to '+' sign)
        password=urlquote(password),
        host=host,
        port=port,
        database=database)

engine = create_engine(db_uri(), listeners=[ForceStrictMode()], echo=False)


def init_db():
    """ Make the tables. """
    from inbox.server.models.tables.base import register_backends
    register_backends()

    Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)


def new_db_session():
    """ Create a new session.

    Most of the time you should be using session_scope() instead, since it
    handles cleanup properly. Sometimes you still need to use this function
    directly because of how context managers require all code using the
    created variable to be in a block; test setup is one example.

    Returns
    -------
    sqlalchemy.orm.session.Session
        The created session.
    """
    from inbox.server.models.tables.base import Transaction, HasRevisions

    return versioned_session(Session(autoflush=True, autocommit=False),
            Transaction, HasRevisions)


@contextmanager
def session_scope():
    """ Provide a transactional scope around a series of operations.

    Takes care of rolling back failed transactions and closing the session
    when it goes out of scope.

    Yields
    ------
    sqlalchemy.orm.session.Session
        The created session.
    """
    session = new_db_session()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()
