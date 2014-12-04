from datetime import datetime, timedelta
import json
from redis import StrictRedis

from inbox.config import config
from inbox.log import get_logger
from inbox.status.key import SyncStatusKey


log = get_logger()


redis_hostname = None
redis_port = None
redis_database = None
redis_client = None


def _get_redis_client():
    global redis_client
    if redis_client is None:
        global redis_hostname
        if redis_hostname is None:
            redis_hostname = config.get('REDIS_HOSTNAME')
        if redis_hostname is None or not isinstance(redis_hostname, str):
            raise Exception('Error while reading REDIS_HOSTNAME')

        global redis_port
        if redis_port is None:
            redis_port = config.get('REDIS_PORT')
        if redis_port is None or not isinstance(redis_port, int):
            raise Exception('Error while reading REDIS_PORT')

        global redis_database
        if redis_database is None:
            redis_database = config.get('REDIS_DATABASE')
        if redis_database is None or not isinstance(redis_database, int) or \
                redis_database < 1 or redis_database > 15:
            raise Exception('Error while reading REDIS_DATABASE')

        redis_client = StrictRedis(host=redis_hostname,
                                   port=redis_port,
                                   db=redis_database)

    return redis_client


class SyncStatus(object):
    schema = set(['provider_name',
                  'folder_name',
                  'heartbeat_at',
                  'state',
                  'action'])

    def __init__(self, account_id, folder_id, device_id=0,
                 alive_threshold=timedelta(seconds=60)):
        self.key = SyncStatusKey(account_id, folder_id)
        self.device_id = device_id
        self.alive_threshold = alive_threshold
        self.heartbeat_at = datetime.min
        self.value = {}
        try:
            global redis_client
            redis_client = _get_redis_client()
        except Exception:
            log.error('Error while initializing the sync status',
                      account_id=account_id,
                      folder_id=folder_id,
                      device_id=device_id,
                      exc_info=True)

    def publish(self, **kwargs):
        now = datetime.utcnow()
        self.value['heartbeat_at'] = str(now)
        for k in kwargs or {}:
            assert k in self.schema
        self.value.update(kwargs or {})
        try:
            global redis_client
            redis_client.hset(self.key, self.device_id, json.dumps(self.value))
            self.heartbeat_at = now
            if 'action' in self.value:
                del self.value['action']
        except Exception:
            log.error('Error while publishing the sync status',
                      account_id=self.key.account_id,
                      folder_id=self.key.folder_id,
                      device_id=self.device_id,
                      exc_info=True)


def del_device(account_id, device_id):
    try:
        global redis_client
        redis_client = _get_redis_client()
        match = SyncStatusKey.all_folders(account_id)
        for k in redis_client.scan_iter(match=match):
            redis_client.hdel(k, device_id)
    except Exception:
        log.error('Error while deleting device from the sync status',
                  account_id=account_id,
                  device_id=device_id,
                  exc_info=True)
