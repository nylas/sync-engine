from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from urllib import quote_plus as urlquote

from ..config import config, is_prod
from ..log import get_logger
log = get_logger()

from .util import ForceStrictMode
from .revision import versioned_session
from .table import Base, Transaction

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

Session = sessionmaker()
Session.configure(bind=engine)

# A single global database session per Inbox instance is good enough for now.
db_session = Session()
versioned_session(db_session, rev_cls=Transaction)
