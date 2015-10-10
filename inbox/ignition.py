import gevent
from socket import gethostname
from urllib import quote_plus as urlquote
from sqlalchemy import create_engine, event

from inbox.sqlalchemy_ext.util import ForceStrictMode
from inbox.config import config
from inbox.util.stats import statsd_client


DB_POOL_SIZE = config.get_required('DB_POOL_SIZE')
# Sane default of max overflow=5 if value missing in config.
DB_POOL_MAX_OVERFLOW = config.get('DB_POOL_MAX_OVERFLOW') or 5
DB_POOL_TIMEOUT = config.get('DB_POOL_TIMEOUT') or 60


# See
# https://github.com/PyMySQL/mysqlclient-python/blob/master/samples/waiter_gevent.py
def gevent_waiter(fd, hub=gevent.hub.get_hub()):
    hub.wait(hub.loop.io(fd, 1))


def build_uri(username, password, hostname, port, database_name):
    uri_template = 'mysql+mysqldb://{username}:{password}@{hostname}' \
                   ':{port}/{database_name}?charset=utf8mb4'
    return uri_template.format(username=urlquote(username),
                               password=urlquote(password),
                               hostname=urlquote(hostname),
                               port=port,
                               database_name=urlquote(database_name))


def engine(database_name, database_uri, pool_size=DB_POOL_SIZE,
           max_overflow=DB_POOL_MAX_OVERFLOW, pool_timeout=DB_POOL_TIMEOUT,
           echo=False):
    engine = create_engine(database_uri,
                           listeners=[ForceStrictMode()],
                           isolation_level='READ COMMITTED',
                           echo=False,
                           pool_size=pool_size,
                           pool_timeout=pool_timeout,
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


class EngineManager(object):
    def __init__(self, shard_params, users):
        self.engines = {}
        for key, params in shard_params.items():
            database_name = params['DATABASE_NAME']
            hostname = params['HOSTNAME']
            port = params['PORT']
            username = users[key]['USER']
            password = users[key]['PASSWORD']
            uri = build_uri(username=username,
                            password=password,
                            database_name=database_name,
                            hostname=hostname,
                            port=port)
            self.engines[int(key)] = engine(database_name, uri)

    def shard_key_for_id(self, id_):
        return id_ >> 48

    def get_for_id(self, id_):
        return self.engines[self.shard_key_for_id(id_)]


engine_manager = EngineManager(config.get_required('DATABASES'),
                               config.get_required('DATABASE_USERS'))


def init_db(engine, key=0):
    """
    Make the tables.

    This is called only from bin/create-db, which is run during setup.
    Previously we allowed this to run everytime on startup, which broke some
    alembic revisions by creating new tables before a migration was run.
    From now on, we should ony be creating tables+columns via SQLalchemy *once*
    and all subsequent changes done via migration scripts.

    """
    from inbox.models.base import MailSyncBase
    from sqlalchemy import event, DDL

    # Hopefully setting auto_increment via an event listener will make it safe
    # to execute this function multiple times.
    # STOPSHIP(emfree): verify
    increment = (key << 48) + 1
    for table in MailSyncBase.metadata.tables.values():
        event.listen(table, 'after_create',
                     DDL('ALTER TABLE {tablename} AUTO_INCREMENT={increment}'.
                         format(tablename=table, increment=increment)))

    MailSyncBase.metadata.create_all(engine)
