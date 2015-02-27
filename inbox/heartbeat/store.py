from datetime import datetime
import time
import json

from inbox.log import get_logger
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
    schema = {'email_address', 'provider_name', 'folder_name',
              'heartbeat_at', 'state', 'action'}

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
        self.publish(email_address=email_address,
                     provider_name=provider_name,
                     folder_name=folder_name)

    @safe_failure
    def publish(self, **kwargs):
        def check_schema(**kwargs):
            for kw in kwargs:
                assert kw in self.schema

        try:
            check_schema(**kwargs)
            self.value.update(kwargs or {})
            # If we got a 'heartbeat_at' datetime argument, publish this
            # heartbeat with that timestamp.
            if 'heartbeat_at' in kwargs and \
                    isinstance(kwargs['heartbeat_at'], datetime):
                epoch = time.mktime(kwargs.get('heartbeat_at').timetuple())
                self.heartbeat_at = epoch
                self.value['heartbeat_at'] = str(kwargs['heartbeat_at'])
            else:
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

    def get_index(self, index, timestamp_threshold=None):
        # Get all elements in the specified index, optionally above the
        # provided timestamp threshold.
        if not timestamp_threshold:
            return self.client.zrange(index, 0, -1, withscores=True)
        else:
            lower_bound = time.time() - timestamp_threshold
            return self.client.zrangebyscore(index, lower_bound, '+inf',
                                             withscores=True)

    def get_folder_list(self, timestamp_threshold=None):
        # Query the folder index for all folders or for all folders which
        # have reported in fewer than timestamp_threshold seconds ago.
        # Returns (folder_id, timestamp) tuples.
        return self.get_index('folder_index', timestamp_threshold)

    def get_account_folders(self, account_id, timestamp_threshold=None):
        return self.get_index(account_id, timestamp_threshold)

    def get_single_folder(self, account_id):
        try:
            folder_id = self.client.zrange(account_id, 0, 0)[0]
        except IndexError:
            return (None, {})
        key = HeartbeatStatusKey(account_id, folder_id)
        folder = self.client.hgetall(key)
        return (folder_id, folder)

    def get_account_timestamp(self, account_id):
        return self.client.zscore('account_index', account_id)

    def get_account_list(self, timestamp_threshold=None):
        # Return all accounts, optionally limited to those with timestamps
        # newer than the provided threshold, in ascending order (by timestamp)
        # Returns (account_id, timestamp) tuples.
        return self.get_index('account_index', timestamp_threshold)

    def get_accounts_below(self, timestamp_threshold):
        # Return all accounts with timestamps older than the provided
        # threshold, in descending order (by timestamp)
        # Returns (account_id, timestamp) tuples.
        upper_bound = time.time() - timestamp_threshold
        return self.client.zrevrangebyscore('account_index',
                                            upper_bound, '-inf',
                                            withscores=True)

    def get_accounts_between(self, lower_time_ago, upper_time_ago):
        # Return all accounts with timestamps between lower_time_ago and
        # upper_time_ago seconds ago, in ascending order by timestamp.
        # Returns (account_id, timestamp) tuples.
        lower_bound = time.time() - lower_time_ago
        upper_bound = time.time() - upper_time_ago
        return self.client.zrangebyscore('account_index', lower_bound,
                                         upper_bound, withscores=True)

    def count_accounts(self, lower_bound=None, upper_bound=None,
                       above=True):
        # Count the number of accounts in the index.
        # :param lower_bound: Only accounts updated since this time
        # :param upper_bound: Only accounts updated before this time (optional)
        # :param above: Show accounts above lower bound (default True)
        if lower_bound:
            lower = time.time() - lower_bound
            if upper_bound:
                upper = time.time() - upper_bound
                return self.client.zcount('account_index', lower, upper)
            # If we only have a lower threshold, count below or above?
            if above:
                return self.client.zcount('account_index', lower, '+inf')
            else:
                return self.client.zcount('account_index', '-inf', lower)
        else:
            return self.client.zcard('account_index')

    def folder_iterator(self, account_id=None, timestamp_threshold=None):
        # Iterate through the folder heartbeat list
        # :param account_id: restrict to folders for account account_id
        # :param timestamp_threshold: restrict to updates since threshold
        if account_id:
            for (k, ts) in self.get_account_folders(account_id):
                # We have to construct a key from this
                yield HeartbeatStatusKey(account_id, k)
        else:
            # getting all folders from the index is cheaper than zscan
            for (f, ts) in self.get_folder_list(timestamp_threshold):
                yield HeartbeatStatusKey.from_string(f)

    def get_folders(self, callback, account_id=None):
        return self.fetch(self.client,
                          lambda c: self.folder_iterator(account_id),
                          lambda p, k: p.hgetall(k),
                          [],
                          callback)

    # Callback is: result = f(key, value)
    def fetch(self, client, scan_cmd, get_cmd, skip_keys=[],
              response_callback=None):
        # Convert a scan operation into a response dictionary of keys: values.
        pipeline = client.pipeline()
        keys = []
        result = {}
        for k in scan_cmd(client):
            if k in skip_keys:
                continue
            get_cmd(pipeline, k)
            keys.append(k)

        values = pipeline.execute()
        pipeline.reset()

        for (k, v) in zip(keys, values):
            if response_callback:
                result[k] = response_callback(k, v)
            else:
                result[k] = v
        return result
