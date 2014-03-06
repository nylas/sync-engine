from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from urllib import quote_plus as urlquote
from contextlib import contextmanager

from ..config import config, is_prod
from ..log import get_logger
log = get_logger()

from .tables import Base, Transaction, HasRevisions

from inbox.sqlalchemy.revision import versioned_session
from inbox.sqlalchemy.util import ForceStrictMode

def db_uri():
    uri_template = 'mysql://{username}:{password}@{host}:{port}/{database}?charset=utf8mb4'

    config_prefix = 'RDS' if is_prod() else 'MYSQL'

    return uri_template.format(
        username = config.get('_'.join([config_prefix, 'USER'])),
        # http://stackoverflow.com/questions/15728290/sqlalchemy-valueerror-for-slash-in-password-for-create-engine (also applicable to '+' sign)
        password = urlquote(config.get('_'.join([config_prefix, 'PASSWORD']))),
        host = config.get('_'.join([config_prefix, 'HOSTNAME'])),
        port = config.get('_'.join([config_prefix, 'PORT'])),
        database = config.get('_'.join([config_prefix, 'DATABASE'])))

engine = create_engine(db_uri(), listeners=[ForceStrictMode()], echo=False)

def init_db():
    """ Make the tables. """
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
