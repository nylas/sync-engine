import random


from inbox.config import config
from inbox.ignition import engine_manager


def get_shards():
    return engine_manager.engines.keys()


def get_open_shards():
    # Can't use engine_manager.engines here because it does not track
    # shard state (open/ closed)
    database_hosts = config.get_required('DATABASE_HOSTS')
    open_shards = []
    for host in database_hosts:
        open_shards.extend(shard['ID'] for shard in host['SHARDS'] if
                           shard['OPEN'] and not shard.get('DISABLED'))

    return open_shards


def get_shard_schemas():
    # Can't use engine_manager.engines here because it does not track
    # shard schemas.
    shard_schemas = {}
    database_hosts = config.get_required('DATABASE_HOSTS')
    for host in database_hosts:
        for shard in host['SHARDS']:
            if not shard.get('DISABLED'):
                shard_id = shard['ID']
                schema_name = shard['SCHEMA_NAME']
                shard_schemas[shard_id] = schema_name
    return shard_schemas


def generate_open_shard_key():
    """
    Return the key that can be passed into session_scope() for an open shard,
    picked at random.

    """
    open_shards = get_open_shards()
    # TODO[k]: Always pick min()instead?
    shard_id = random.choice(open_shards)
    key = shard_id << 48
    return key
