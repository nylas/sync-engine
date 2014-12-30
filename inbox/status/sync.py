from collections import namedtuple
from datetime import datetime, timedelta
import json
from redis import StrictRedis

from inbox.config import config
from inbox.log import get_logger


ALIVE_THRESHOLD = 180
ALIVE_THRESHOLD_CONTACTS = 420
ALIVE_THRESHOLD_EVENTS = 420
ALIVE_THRESHOLD_EAS = 420


AliveThresholds = namedtuple('AliveThresholds',
                             ['base', 'contacts', 'events', 'eas'])
g_alive_thresholds = None


def get_heartbeat_config():
    global g_alive_thresholds
    if not g_alive_thresholds:
        base = int(config.get_required('ALIVE_THRESHOLD'))
        contacts = int(config.get_required('ALIVE_THRESHOLD_CONTACTS'))
        events = int(config.get_required('ALIVE_THRESHOLD_EVENTS'))
        eas = int(config.get_required('ALIVE_THRESHOLD_EAS'))

        g_alive_thresholds = AliveThresholds(
            timedelta(seconds=base),
            timedelta(seconds=contacts),
            timedelta(seconds=events),
            timedelta(seconds=eas)
        )

    return g_alive_thresholds


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
    def contacts(cls, account_id):
        return cls(account_id, '-1')

    @classmethod
    def events(cls, account_id):
        return cls(account_id, '-2')

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
        client_batch = client.pipeline()
        match_key = SyncStatusKey.all_folders(account_id)
        for k in client.scan_iter(match=match_key):
            client_batch.hdel(k, device_id)
        client_batch.execute()
    except Exception:
        log = get_logger()
        log.error('Error while deleting from the sync status',
                  account_id=account_id,
                  device_id=device_id,
                  exc_info=True)


def has_contacts_events(account_id):
    try:
        client = get_redis_client()
        client_batch = client.pipeline()
        client_batch.keys(pattern=SyncStatusKey.contacts(account_id))
        client_batch.keys(pattern=SyncStatusKey.events(account_id))
        values = client_batch.execute()
        return (len(values[0]) == 1, len(values[1]) == 1)
    except Exception:
        log = get_logger()
        log.error('Error while reading from the sync status',
                  account_id=account_id,
                  exc_info=True)
        return (False, False)


def get_sync_status(hostname=None, port=6379, database=1,
                    alive_thresholds=AliveThresholds(
                        timedelta(seconds=ALIVE_THRESHOLD),
                        timedelta(seconds=ALIVE_THRESHOLD_CONTACTS),
                        timedelta(seconds=ALIVE_THRESHOLD_EVENTS),
                        timedelta(seconds=ALIVE_THRESHOLD_EAS)
                    ),
                    account_id=None):
    if hostname:
        client = StrictRedis(host=hostname, port=port, db=database)
    else:
        client = get_redis_client()
        alive_thresholds = get_heartbeat_config()
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

            if key.folder_id == -1:
                # contacts
                device_alive = (now - heartbeat_at) < alive_thresholds.contacts
            elif key.folder_id == -2:
                # events
                device_alive = (now - heartbeat_at) < alive_thresholds.events
            elif provider_name == 'eas' and action == 'ping':
                # eas w/ ping
                device_alive = (now - heartbeat_at) < alive_thresholds.eas
            else:
                device_alive = (now - heartbeat_at) < alive_thresholds.base
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
