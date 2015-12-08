from datetime import datetime
import time
import json

from nylas.logging import get_logger
log = get_logger()
from inbox.heartbeat.config import (CONTACTS_FOLDER_ID, EVENTS_FOLDER_ID,
                                    get_redis_client)


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
        self.heartbeat_at = datetime.min
        self.store = HeartbeatStore.store()
        self.value = {}
        self.email_address = email_address

    @safe_failure
    def publish(self, **kwargs):
        try:
            self.value.update(kwargs or {})
            self.heartbeat_at = time.time()
            self.value['heartbeat_at'] = str(datetime.fromtimestamp(
                self.heartbeat_at))
            self.store.publish(
                self.key, self.device_id, json.dumps(self.value),
                self.heartbeat_at)
            if 'action' in self.value:
                del self.value['action']
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
    client = None

    def __init__(self, host=None, port=6379):
        self.client = get_redis_client(host, port)

    @classmethod
    def store(cls, host=None, port=None):
        # Allow singleton access to the store, keyed by host.
        if cls._instances.get(host) is None:
            cls._instances[host] = cls(host, port)
        return cls._instances.get(host)

    @safe_failure
    def publish(self, key, device_id, value, timestamp=None):
        if not timestamp:
            timestamp = time.time()
        # Publish a heartbeat update for the given key and device_id.
        self.client.hset(key, device_id, value)
        # Update indexes
        self.update_folder_index(key, float(timestamp))
        self.update_accounts_index(key)

    def remove(self, key, device_id=None, client=None):
        # Remove a key from the store, or device entry from a key.
        if not client:
            client = self.client
        if device_id:
            client.hdel(key, device_id)
            # If that was the only entry, also remove from folder index.
            devices = self.client.hkeys(key)
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
            pipeline = self.client.pipeline()
            n = 0
            for key in self.client.scan_iter(match, 100):
                self.remove(key, device_id, pipeline)
                n += 1
            if not device_id:
                self.remove_from_account_index(account_id, pipeline)
            pipeline.execute()
            pipeline.reset()
            return n

    def update_folder_index(self, key, timestamp):
        assert isinstance(timestamp, float)
        # Update a sorted set by timestamp for super easy key retrieval.
        self.client.zadd('folder_index', timestamp, key)
        # Update the folder timestamp index for this specific account, too
        self.client.zadd(key.account_id, timestamp, key.folder_id)

    def update_accounts_index(self, key):
        # Find the oldest heartbeat from the account-folder index
        try:
            f, oldest_heartbeat = self.client.zrange(key.account_id, 0, 0,
                                                     withscores=True).pop()
            self.client.zadd('account_index', oldest_heartbeat, key.account_id)
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

    def get_index(self, index):
        # Get all elements in the specified index.
        return self.client.zrange(index, 0, -1, withscores=True)

    def get_account_folders(self, account_id):
        return self.get_index(account_id)

    def get_accounts_folders(self, account_ids):
        # Preferred method of querying for multiple accounts. Uses pipelining
        # to reduce the number of requests to redis.
        pipe = self.client.pipeline()
        for index in account_ids:
            pipe.zrange(index, 0, -1, withscores=True)
        return pipe.execute()
