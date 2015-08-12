import gevent
from socket import gethostname
from sqlalchemy import create_engine, event

from inbox.sqlalchemy_ext.util import ForceStrictMode
from inbox.config import engine_uri, config
from inbox.util.stats import statsd_client

DB_POOL_SIZE = config.get_required('DB_POOL_SIZE')
# Sane default of max overflow=5 if value missing in config.
DB_POOL_MAX_OVERFLOW = config.get('DB_POOL_MAX_OVERFLOW') or 5


# See
# https://github.com/PyMySQL/mysqlclient-python/blob/master/samples/waiter_gevent.py
def gevent_waiter(fd, hub=gevent.hub.get_hub()):
    hub.wait(hub.loop.io(fd, 1))


def main_engine(pool_size=DB_POOL_SIZE, max_overflow=DB_POOL_MAX_OVERFLOW,
                echo=False):
    database_name = config.get_required('MYSQL_DATABASE')
    engine = create_engine(engine_uri(database_name),
                           listeners=[ForceStrictMode()],
                           isolation_level='READ COMMITTED',
                           echo=echo,
                           pool_size=pool_size,
                           pool_recycle=3600,
                           max_overflow=max_overflow,
                           connect_args={'charset': 'utf8mb4',
                                         'waiter': gevent_waiter})

    @event.listens_for(engine, 'checkout')
    def receive_checkout(dbapi_connection, connection_record,
                         connection_proxy):
        '''Log checkedout and overflow when a connection is checked out'''
        hostname = gethostname().replace(".", "-")
        process_name = str(config.get("PROCESS_NAME", "unknown"))

        statsd_client.gauge(".".join(
            ["dbconn", database_name, hostname, process_name,
             "checkedout"]),
            connection_proxy._pool.checkedout())

        statsd_client.gauge(".".join(
            ["dbconn", database_name, hostname, process_name,
             "overflow"]),
            connection_proxy._pool.overflow())

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
