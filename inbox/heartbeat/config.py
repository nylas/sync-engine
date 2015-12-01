from redis import StrictRedis, BlockingConnectionPool

from inbox.config import config

STATUS_DATABASE = 1
REPORT_DATABASE = 2

ALIVE_EXPIRY = int(config.get('BASE_ALIVE_THRESHOLD', 480))

CONTACTS_FOLDER_ID = '-1'
EVENTS_FOLDER_ID = '-2'

MAX_CONNECTIONS = 100
WAIT_TIMEOUT = 5
SOCKET_TIMEOUT = 60

connection_pool = None


def _get_connection_pool():
    # get_redis_client() is called once per sync process at the time of
    # instantiating the singleton HeartBeatStore, so doing this here
    # should be okay for now.
    # TODO[k]: Refactor.
    global connection_pool
    if connection_pool is None:
        connection_pool = BlockingConnectionPool(
            max_connections=MAX_CONNECTIONS, timeout=WAIT_TIMEOUT,
            socket_timeout=SOCKET_TIMEOUT)
    assert connection_pool is not None
    return connection_pool


def get_redis_client(host=None, port=6379, db=STATUS_DATABASE):
    if not host:
        host = str(config.get_required('REDIS_HOSTNAME'))
        port = int(config.get_required('REDIS_PORT'))
    connection_pool = _get_connection_pool()
    return StrictRedis(host, port, db, connection_pool=connection_pool)
