from datetime import datetime
import json

from inbox.log import get_logger
from inbox.heartbeat.config import (STATUS_DATABASE,
                                    get_alive_thresholds, get_redis_client,
                                    _get_alive_thresholds, _get_redis_client)


CONTACTS_FOLDER_ID = '-1'
EVENTS_FOLDER_ID = '-2'


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

    def __init__(self, account_id, folder_id, device_id=0):
        self.key = HeartbeatStatusKey(account_id, folder_id)
        self.device_id = device_id
        self.heartbeat_at = datetime.min
        self.value = {}

    def publish(self, **kwargs):
        schema = {'email_address', 'provider_name', 'folder_name',
                  'heartbeat_at', 'state', 'action'}

        def check_schema(**kwargs):
            for kw in kwargs:
                assert kw in schema

        try:
            client = get_redis_client(STATUS_DATABASE)
            check_schema(**kwargs)
            now = datetime.utcnow()
            self.value['heartbeat_at'] = str(now)
            self.value.update(kwargs or {})
            client.hset(self.key, self.device_id, json.dumps(self.value))
            self.heartbeat_at = now
            if 'action' in self.value:
                del self.value['action']
        except Exception:
            log = get_logger()
            log.error('Error while writing the heartbeat status',
                      account_id=self.key.account_id,
                      folder_id=self.key.folder_id,
                      device_id=self.device_id,
                      exc_info=True)


class DeviceHeartbeatStatus(object):

    def __init__(self):
        self.alive = True
        self.state = None
        self.heartbeat_at = None

    def jsonify(self):
        return {'alive': self.alive,
                'state': self.state,
                'heartbeat_at': str(self.heartbeat_at)}


class FolderHeartbeatStatus(object):

    def __init__(self):
        self.alive = True
        self.name = ''
        self.devices = {}

    @property
    def initial_sync(self):
        return any(device.state == 'initial'
                   for device in self.devices.itervalues())

    @property
    def poll_sync(self):
        return all(device.state == 'poll'
                   for device in self.devices.itervalues())

    def jsonify(self):
        return {'alive': self.alive,
                'name': self.name,
                'devices': {device_id: device.jsonify()
                            for device_id, device in self.devices.iteritems()}}


class AccountHeartbeatStatus(object):

    def __init__(self, missing=False):
        self.missing = missing
        self.alive = not self.missing
        self.email_address = ''
        self.provider_name = ''
        self.folders = {}

    @property
    def dead_folders(self):
        return [folder.name
                for folder in self.folders.itervalues() if not folder.alive]

    @property
    def initial_sync(self):
        return any(folder.initial_sync for folder in self.folders.itervalues())

    @property
    def poll_sync(self):
        return all(folder.poll_sync for folder in self.folders.itervalues())

    def jsonify(self):
        return {'missing': self.missing,
                'alive': self.alive,
                'email_address': self.email_address,
                'provider_name': self.provider_name,
                'folders': {folder_id: folder.jsonify()
                            for folder_id, folder in self.folders.iteritems()}}


def get_heartbeat_status(host=None, port=6379, account_id=None):
    if host:
        thresholds = _get_alive_thresholds()
        client = _get_redis_client(host, port, STATUS_DATABASE)
    else:
        thresholds = get_alive_thresholds()
        client = get_redis_client(STATUS_DATABASE)
    batch_client = client.pipeline()

    keys = []
    match_key = None
    if account_id:
        match_key = HeartbeatStatusKey.all_folders(account_id)
    for k in client.scan_iter(match=match_key, count=100):
        if k == 'ElastiCacheMasterReplicationTimestamp':
            continue
        batch_client.hgetall(k)
        keys.append(k)
    values = batch_client.execute()

    now = datetime.utcnow()

    accounts = {}
    for (k, v) in zip(keys, values):
        key = HeartbeatStatusKey.from_string(k)

        account = accounts.get(key.account_id, AccountHeartbeatStatus())
        folder = account.folders.get(key.folder_id, FolderHeartbeatStatus())

        for device_id in v:
            value = json.loads(v[device_id])

            # eventually overwrite the following two fields, no big deal
            account.email_address = value['email_address']
            account.provider_name = value['provider_name']
            folder.name = value['folder_name']

            device = DeviceHeartbeatStatus()
            device.heartbeat_at = datetime.strptime(value['heartbeat_at'],
                                                    '%Y-%m-%d %H:%M:%S.%f')
            device.state = value.get('state', None)

            action = value.get('action', None)

            if key.folder_id == CONTACTS_FOLDER_ID:
                device.alive = (now - device.heartbeat_at) < \
                    thresholds.contacts
            elif key.folder_id == EVENTS_FOLDER_ID:
                device.alive = (now - device.heartbeat_at) < thresholds.events
            elif account.provider_name == 'eas' and action == 'throttled':
                device.alive = (now - device.heartbeat_at) < \
                    thresholds.eas_throttled
            elif account.provider_name == 'eas' and action == 'ping':
                device.alive = (now - device.heartbeat_at) < \
                    thresholds.eas_ping
            else:
                device.alive = (now - device.heartbeat_at) < thresholds.base
            device.alive = device.alive and \
                (device.state in {None, 'initial', 'poll'})

            folder.devices[int(device_id)] = device

            # a folder is alive if and only if all the devices handling that
            # folder are alive
            folder.alive = folder.alive and device.alive
            account.folders[key.folder_id] = folder

            # an account is alive if and only if all the folders of the account
            # are alive
            account.alive = account.alive and folder.alive
            accounts[key.account_id] = account

    if account_id and account_id not in accounts:
        accounts[account_id] = AccountHeartbeatStatus(missing=True)

    return accounts


def clear_heartbeat_status(account_id, folder_id=None, device_id=None):
    try:
        client = get_redis_client(STATUS_DATABASE)
        batch_client = client.pipeline()
        if folder_id:
            match_name = HeartbeatStatusKey(account_id, folder_id)
        else:
            match_name = HeartbeatStatusKey.all_folders(account_id)
        for name in client.scan_iter(match_name, 100):
            if device_id:
                batch_client.hdel(name, device_id)
            else:
                batch_client.delete(name)
        batch_client.execute()
    except Exception:
        log = get_logger()
        log.error('Error while deleting from the heartbeat status',
                  account_id=account_id,
                  folder_id=(folder_id or 'all'),
                  device_id=(device_id or 'all'),
                  exc_info=True)
