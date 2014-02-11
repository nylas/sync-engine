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

engine = create_engine(db_uri(), listeners=[ForceStrictMode()])

def init_db():
    """ Make the tables. """
    Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)

# This returns a new session whenever it's called.
# session_scope uses a registry to return the _same_ session if it's in the
# same thread, otherwise a new session.
def new_db_session():
    return versioned_session(Session(autoflush=True, autocommit=False),
            Transaction, HasRevisions)

@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    session = new_db_session()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()
