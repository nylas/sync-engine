import gevent
from socket import gethostname
from urllib import quote_plus as urlquote
import MySQLdb
import sqlalchemy.pool
from sqlalchemy import create_engine, event

from inbox.sqlalchemy_ext.util import ForceStrictMode
from inbox.config import config
from inbox.util.stats import statsd_client
from nylas.logging import get_logger
from warnings import filterwarnings
filterwarnings('ignore', message='Invalid utf8mb4 character string')
log = get_logger()


DB_POOL_SIZE = config.get_required('DB_POOL_SIZE')
# Sane default of max overflow=5 if value missing in config.
DB_POOL_MAX_OVERFLOW = config.get('DB_POOL_MAX_OVERFLOW') or 5
DB_POOL_TIMEOUT = config.get('DB_POOL_TIMEOUT') or 60


# See
# https://github.com/PyMySQL/mysqlclient-python/blob/master/samples/waiter_gevent.py
def gevent_waiter(fd, hub=gevent.hub.get_hub()):
    hub.wait(hub.loop.io(fd, 1))


def build_uri(username, password, hostname, port):
    uri_template = 'mysql+mysqldb://{username}:{password}@{hostname}' \
                   ':{port}/?charset=utf8mb4'
    return uri_template.format(username=urlquote(username),
                               password=urlquote(password),
                               hostname=urlquote(hostname),
                               port=port)


def engine(schema_name, host_uri, pool):
    engine = create_engine(host_uri, pool=pool,
                           isolation_level='READ COMMITTED',
                           connect_args={'charset': 'utf8mb4',
                                         'waiter': gevent_waiter})

    @event.listens_for(engine, 'engine_connect')
    def choose_schema(conn, branch):
        # Issue a `USE <schema_name>` statement for the right shard if it's not
        # already selected. Note that this must be registered as an
        # `engine_connect` listener, because `checkout` listeners are attached
        # directly to engine.pool, and hence cannot maintain engine-specific
        # state if multiple engines share an underlying pool.
        if conn.info.get('selected_db') != schema_name:
            conn.connection.select_db(schema_name)
            conn.info['selected_db'] = schema_name

    @event.listens_for(engine, 'before_execute')
    def check(*args, **kwargs):
        # TODO(emfree): implement or discard.
        pass


    @event.listens_for(engine, 'checkout')
    def receive_checkout(dbapi_connection, connection_record,
                         connection_proxy):
        hostname = gethostname().replace(".", "-")
        process_name = str(config.get("PROCESS_NAME", "unknown"))

        # Log pool checkedout and overflow metrics
        statsd_client.gauge(".".join(
            ["dbconn", schema_name, hostname, process_name,
             "checkedout"]),
            connection_proxy._pool.checkedout())

        statsd_client.gauge(".".join(
            ["dbconn", schema_name, hostname, process_name,
             "overflow"]),
            connection_proxy._pool.overflow())

    return engine


class EngineManager(object):
    """ The EngineManager is responsible for, well, managing a collection of
    SQLAlchemy engines, one for each configured shard. In general, only one of
    these should be instantiated per process."""
    def __init__(self, databases, users, include_disabled=False):
        # Multiple shards can live on one MySQL instance. The engines for
        # different shards on one instance share an underlying connection pool;
        # we dynamically select the right shard on checkout.  To this end,
        # self._pool_proxy here is an instance of sqlalchemy.pool._DBProxy:
        # when passed to an engine constructor, it resolves to a single
        # QueuePool instance for each distinct set of connection arguments,
        # giving the desired pool-sharing behavior.
        self._pool_proxy = sqlalchemy.pool.manage(
            MySQLdb, pool_size=DB_POOL_SIZE, max_overflow=DB_POOL_MAX_OVERFLOW,
            timeout=DB_POOL_TIMEOUT,
            listeners=[ForceStrictMode()]
        )
        self.engines = {}
        keys = set()
        schema_names = set()
        for database in databases:
            hostname = database['HOSTNAME']
            port = database['PORT']
            username = users[hostname]['USER']
            password = users[hostname]['PASSWORD']
            for shard in database['SHARDS']:
                schema_name = shard['SCHEMA_NAME']
                key = shard['ID']

                # Perform some sanity checks on the configuration.
                assert isinstance(key, int)
                assert key not in keys, \
                    'Shard key collision: key {} is repeated'.format(key)
                assert schema_name not in schema_names, \
                    'Shard name collision: {} is repeated'.format(schema_name)
                keys.add(key)
                schema_names.add(schema_name)

                if shard.get('DISABLED') and not include_disabled:
                    log.info('Not creating engine for disabled shard',
                             schema_name=schema_name, hostname=hostname,
                             key=key)
                    continue

                host_uri = build_uri(username=username,
                                     password=password,
                                     hostname=hostname,
                                     port=port)
                self.engines[key] = engine(schema_name, host_uri,
                                           pool=self._pool_proxy)

    def shard_key_for_id(self, id_):
        return id_ >> 48

    def get_for_id(self, id_):
        return self.engines[self.shard_key_for_id(id_)]

engine_manager = EngineManager(config.get_required('DATABASE_HOSTS'),
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


def verify_db(engine, schema, key):
    from inbox.models.base import MailSyncBase

    query = """SELECT AUTO_INCREMENT from information_schema.TABLES where
    table_schema='{}' AND table_name='{}';"""

    verified = set()
    for table in MailSyncBase.metadata.sorted_tables:
        increment = engine.execute(query.format(schema, table)).scalar()
        if increment is not None:
            assert (increment >> 48) == key, \
                'table: {}, increment: {}, key: {}'.format(table, increment, key)
        else:
            # We leverage the following invariants about the sync schema to make
            # the assertion below: one, in the sync schema, a table's id column
            # is assigned the auto_increment since we use this column as the
            # primary_key. Two, the only tables that have a None auto_increment
            # are inherited tables (like '*account', '*thread' '*actionlog',
            # 'recurringevent*'), because their id column is instead a
            # foreign_key on their parent's id column.
            parent = list(table.columns['id'].foreign_keys)[0].column.table
            assert parent in verified
        verified.add(table)
