from datetime import datetime, timedelta
import json
from redis import StrictRedis

from inbox.config import config
from inbox.log import get_logger


g_alive_threshold = None
g_alive_threshold_eas = None


def get_heartbeat_config():
    global g_alive_threshold
    if g_alive_threshold is None:
        g_alive_threshold = int(config.get_required('ALIVE_THRESHOLD'))

    global g_alive_threshold_eas
    if g_alive_threshold_eas is None:
        g_alive_threshold_eas = int(config.get_required('ALIVE_THRESHOLD_EAS'))

    return (g_alive_threshold, g_alive_threshold_eas)


redis_hostname = None
redis_port = None
redis_database = None
redis_client = None


def get_redis_client():
    global redis_client
    if redis_client is None:
        global redis_hostname
        if redis_hostname is None:
            redis_hostname = str(config.get_required('REDIS_HOSTNAME'))

        global redis_port
        if redis_port is None:
            redis_port = int(config.get_required('REDIS_PORT'))

        global redis_database
        if redis_database is None:
            redis_database = int(config.get_required('REDIS_DATABASE'))
            assert redis_database >= 1 and redis_database <= 15

        redis_client = StrictRedis(host=redis_hostname,
                                   port=redis_port,
                                   db=redis_database)

    return redis_client


class SyncStatusKey(object):
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

    def __le__(self, other):
        if self.account_id != other.account_id:
            return self.account_id < other.account_id
        return self.folder_id <= other.folder_id

    def __eq__(self, other):
        return self.account_id == other.account_id and \
            self.folder_id == other.folder_id

    def __ne__(self, other):
        return self.account_id != other.account_id or \
            self.folder_id != other.folder_id

    def __gt__(self, other):
        if self.account_id != other.account_id:
            return self.account_id > other.account_id
        return self.folder_id > other.folder_id

    def __ge__(self, other):
        if self.account_id != other.account_id:
            return self.account_id > other.account_id
        return self.folder_id >= other.folder_id

    @classmethod
    def all_folders(cls, account_id):
        return cls(account_id, '*')

    @classmethod
    def from_string(cls, string_key):
        account_id, folder_id = map(int, string_key.split(':'))
        return cls(account_id, folder_id)


redis_schema = set(['provider_name',
                    'folder_name',
                    'heartbeat_at',
                    'state',
                    'action'])


def _check_redis_schema(**kwargs):
    for kw in kwargs:
        assert kw in redis_schema


class SyncStatus(object):
    def __init__(self, account_id, folder_id, device_id=0):
        self.key = SyncStatusKey(account_id, folder_id)
        self.device_id = device_id
        self.heartbeat_at = datetime.min
        self.value = {}

    def publish(self, **kwargs):
        try:
            client = get_redis_client()
            _check_redis_schema(**kwargs)
            now = datetime.utcnow()
            self.value['heartbeat_at'] = str(now)
            self.value.update(kwargs or {})
            client.hset(self.key, self.device_id, json.dumps(self.value))
            self.heartbeat_at = now
            if 'action' in self.value:
                del self.value['action']
        except Exception:
            log = get_logger()
            log.error('Error while publishing the sync status',
                      account_id=self.key.account_id,
                      folder_id=self.key.folder_id,
                      device_id=self.device_id,
                      exc_info=True)


def del_device(account_id, device_id):
    try:
        client = get_redis_client()
        match_key = SyncStatusKey.all_folders(account_id)
        for k in client.scan_iter(match=match_key):
            client.hdel(k, device_id)
    except Exception:
        log = get_logger()
        log.error('Error while deleting from the sync status',
                  account_id=account_id,
                  device_id=device_id,
                  exc_info=True)


def get_sync_status(hostname=None, port=6379, database=1,
                    alive_threshold=timedelta(seconds=180),
                    alive_threshold_eas=timedelta(seconds=420),
                    account_id=None):
    if hostname:
        client = StrictRedis(host=hostname, port=port, db=database)
    else:
        try:
            client = get_redis_client()
            alive_threshold_eas, alive_threshold_eas = get_heartbeat_config()
        except Exception as e:
            raise e
    client_batch = client.pipeline()

    keys = []
    match_key = None
    if account_id:
        match_key = SyncStatusKey.all_folders(account_id)
    for k in client.scan_iter(match=match_key, count=100):
        # this shouldn't happen since we won't use db=0 anymore
        if k == 'ElastiCacheMasterReplicationTimestamp':
            continue
        client_batch.hgetall(k)
        keys.append(k)
    values = client_batch.execute()

    now = datetime.utcnow()
    alive_threshold = timedelta(seconds=180)
    alive_threshold_eas = timedelta(seconds=420)

    accounts = {}
    for (k, v) in zip(keys, values):
        key = SyncStatusKey.from_string(k)
        account_alive, provider_name, folders = accounts.get(key.account_id,
                                                             (True, '', {}))
        folder_alive, folder_name, devices = folders.get(key.folder_id,
                                                         (True, '', {}))

        for device_id in v:
            value = json.loads(v[device_id])

            provider_name = value['provider_name']
            folder_name = value['folder_name']

            heartbeat_at = datetime.strptime(value['heartbeat_at'],
                                             '%Y-%m-%d %H:%M:%S.%f')
            state = value.get('state', None)
            action = value.get('action', None)

            if provider_name != 'eas' or \
                    (provider_name == 'eas' and action != 'ping'):
                device_alive = (now - heartbeat_at) < alive_threshold
            else:
                device_alive = (now - heartbeat_at) < alive_threshold_eas
            device_alive = device_alive and \
                (state in set([None, 'initial', 'poll']))

            devices[int(device_id)] = {'heartbeat_at': str(heartbeat_at),
                                       'state': state,
                                       'action': action,
                                       'alive': device_alive}

            # a folder is alive if and only if all the devices handling that
            # folder are alive
            folder_alive = folder_alive and device_alive

            folders[key.folder_id] = (folder_alive, folder_name, devices)

            # an account is alive if and only if all the folders of the account
            # are alive
            account_alive = account_alive and folder_alive

            accounts[key.account_id] = (account_alive, provider_name, folders)

    return accounts
