import time
import itertools
from inbox.util.itert import chunk

from nylas.logging import get_logger
log = get_logger()

# We're doing this weird rename import to make it easier to monkeypatch
# get_redis_client. That's the only way we have to test our very brittle
# status code.
import inbox.heartbeat.config as heartbeat_config
from inbox.heartbeat.config import (CONTACTS_FOLDER_ID, EVENTS_FOLDER_ID)


def safe_failure(f):
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception:
            log.error('Error interacting with heartbeats',
                      exc_info=True)
    return wrapper


class HeartbeatStatusKey(object):

    def __init__(self, account_id, folder_id):
        self.account_id = account_id
        self.folder_id = folder_id
        self.key = '{}:{}'.format(self.account_id, self.folder_id)

    def __repr__(self):
        return self.key

    def __lt__(self, other):
        if self.account_id != other.account_id:
            return self.account_id < other.account_id
        return self.folder_id < other.folder_id

    def __eq__(self, other):
        return self.account_id == other.account_id and \
            self.folder_id == other.folder_id

    @classmethod
    def all_folders(cls, account_id):
        return cls(account_id, '*')

    @classmethod
    def contacts(cls, account_id):
        return cls(account_id, CONTACTS_FOLDER_ID)

    @classmethod
    def events(cls, account_id):
        return cls(account_id, EVENTS_FOLDER_ID)

    @classmethod
    def from_string(cls, string_key):
        account_id, folder_id = map(int, string_key.split(':'))
        return cls(account_id, folder_id)


class HeartbeatStatusProxy(object):
    def __init__(self, account_id, folder_id, folder_name=None,
                 email_address=None, provider_name=None, device_id=0):
        self.key = HeartbeatStatusKey(account_id, folder_id)
        self.account_id = account_id
        self.folder_id = folder_id
        self.device_id = device_id
        self.store = HeartbeatStore.store()

    @safe_failure
    def publish(self, **kwargs):
        try:
            self.heartbeat_at = time.time()
            self.store.publish(self.key, self.heartbeat_at)
        except Exception:
            log = get_logger()
            log.error('Error while writing the heartbeat status',
                      account_id=self.key.account_id,
                      folder_id=self.key.folder_id,
                      device_id=self.device_id,
                      exc_info=True)

    @safe_failure
    def clear(self):
        self.store.remove_folders(self.account_id, self.folder_id,
                                  self.device_id)


class HeartbeatStore(object):
    """ Store that proxies requests to Redis with handlers that also
        update indexes and handle scanning through results. """
    _instances = {}

    def __init__(self, host=None, port=6379):
        self.host = host
        self.port = port

    @classmethod
    def store(cls, host=None, port=None):
        # Allow singleton access to the store, keyed by host.
        if cls._instances.get(host) is None:
            cls._instances[host] = cls(host, port)
        return cls._instances.get(host)

    @safe_failure
    def publish(self, key, timestamp):
        # Update indexes
        self.update_folder_index(key, float(timestamp))

    def remove(self, key, device_id=None):
        # Remove a key from the store, or device entry from a key.
        client = heartbeat_config.get_redis_client(key.account_id)

        if device_id:
            client.hdel(key, device_id)
            # If that was the only entry, also remove from folder index.
            devices = client.hkeys(key)
            if devices == [str(device_id)] or devices == []:
                self.remove_from_folder_index(key, client)
        else:
            client.delete(key)
            self.remove_from_folder_index(key, client)

    @safe_failure
    def remove_folders(self, account_id, folder_id=None, device_id=None):
        # Remove heartbeats for the given account, folder and/or device.
        if folder_id:
            key = HeartbeatStatusKey(account_id, folder_id)
            self.remove(key, device_id)
            # Update the account's oldest heartbeat after deleting a folder
            self.update_accounts_index(key)
            return 1  # 1 item removed
        else:
            # Remove all folder timestamps and account-level indices
            match = HeartbeatStatusKey.all_folders(account_id)

            client = heartbeat_config.get_redis_client(account_id)
            pipeline = client.pipeline()
            n = 0
            for key in client.scan_iter(match, 100):
                self.remove(key, device_id, pipeline)
                n += 1
            if not device_id:
                self.remove_from_account_index(account_id, pipeline)
            pipeline.execute()
            pipeline.reset()
            return n

    def update_folder_index(self, key, timestamp):
        assert isinstance(timestamp, float)
        # Update the folder timestamp index for this specific account, too
        client = heartbeat_config.get_redis_client(key.account_id)
        client.zadd(key.account_id, timestamp, key.folder_id)

    def update_accounts_index(self, key):
        # Find the oldest heartbeat from the account-folder index
        try:
            client = heartbeat_config.get_redis_client(key.account_id)
            f, oldest_heartbeat = client.zrange(key.account_id, 0, 0,
                                                withscores=True).pop()
            client.zadd('account_index', oldest_heartbeat, key.account_id)
        except:
            # If all heartbeats were deleted at the same time as this, the pop
            # will fail -- ignore it.
            pass

    def remove_from_folder_index(self, key, client):
        client.zrem('folder_index', key)
        if isinstance(key, str):
            key = HeartbeatStatusKey.from_string(key)
        client.zrem(key.account_id, key.folder_id)

    def remove_from_account_index(self, account_id, client):
        client.delete(account_id)
        client.zrem('account_index', account_id)

    def get_account_folders(self, account_id):
        client = heartbeat_config.get_redis_client(account_id)
        return client.zrange(account_id, 0, -1, withscores=True)

    def get_accounts_folders(self, account_ids):
        # This is where things get interesting --- we need to make queries
        # to multiple shards and return the results to a single caller.
        # Preferred method of querying for multiple accounts. Uses pipelining
        # to reduce the number of requests to redis.
        account_ids_grouped_by_shards = []

        # A magic one-liner to group account ids by shard.
        # http://stackoverflow.com/questions/8793772/how-to-split-a-sequence-according-to-a-predicate
        shard_num = heartbeat_config.account_redis_shard_number
        account_ids_grouped_by_shards = [list(v[1]) for v in
                                         itertools.groupby(
            sorted(account_ids, key=shard_num),
            key=shard_num)]

        results = dict()
        for account_group in account_ids_grouped_by_shards:
            if not account_group:
                continue

            client = heartbeat_config.get_redis_client(account_group[0])

            # Because of the way pipelining works, redis buffers data.
            # We break our requests in chunk to not have to ask for
            # impossibly big numbers.
            for chnk in chunk(account_group, 10000):
                pipe = client.pipeline()
                for index in chnk:
                    pipe.zrange(index, 0, -1, withscores=True)

                pipe_results = pipe.execute()

                for i, account_id in enumerate(chnk):
                    account_id = int(account_id)
                    results[account_id] = pipe_results[i]

        return results
