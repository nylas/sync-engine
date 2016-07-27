from redis import StrictRedis, BlockingConnectionPool

from inbox.config import config

STATUS_DATABASE = 1

ALIVE_EXPIRY = int(config.get('BASE_ALIVE_THRESHOLD', 480))
REDIS_SHARDS = config.get('REDIS_SHARDS')
REDIS_PORT = int(config.get('REDIS_PORT'))

CONTACTS_FOLDER_ID = '-1'
EVENTS_FOLDER_ID = '-2'

MAX_CONNECTIONS = 70
WAIT_TIMEOUT = 15
SOCKET_TIMEOUT = 60

assert REDIS_SHARDS is not None, "REDIS_SHARDS is None. Did you set INBOX_ENV?"
connection_pool_map = {instance_name: None for instance_name in REDIS_SHARDS}


def _get_redis_connection_pool(host, port, db):
    # This function is called once per sync process at the time of
    # instantiating the singleton HeartBeatStore, so doing this here
    # should be okay for now.
    # TODO[k]: Refactor.
    global connection_pool_map

    connection_pool = connection_pool_map.get(host)
    if connection_pool is None:
        connection_pool = BlockingConnectionPool(
            host=host, port=port, db=db,
            max_connections=MAX_CONNECTIONS, timeout=WAIT_TIMEOUT,
            socket_timeout=SOCKET_TIMEOUT)
        connection_pool_map[host] = connection_pool

    return connection_pool


def account_redis_shard_number(account_id):
    return account_id % len(REDIS_SHARDS)


def get_redis_client(account_id):
    account_shard_number = account_redis_shard_number(account_id)
    host = REDIS_SHARDS[account_shard_number]

    connection_pool = _get_redis_connection_pool(host, REDIS_PORT,
                                                 STATUS_DATABASE)
    return StrictRedis(host, REDIS_PORT, STATUS_DATABASE,
                       connection_pool=connection_pool)
