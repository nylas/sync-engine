from datetime import datetime, timedelta
from redis import StrictRedis

from inbox.config import config
from inbox.log import get_logger


redis_hostname = None
redis_port = None
redis_client = None


log = get_logger()


def _get_redis_client():
    global redis_hostname
    if redis_hostname is None:
        redis_hostname = config.get('REDIS_HOSTNAME')

    global redis_port
    if redis_port is None:
        redis_port = config.get('REDIS_PORT')

    global redis_client
    if redis_client is None:
        redis_client = StrictRedis(host=redis_hostname, port=redis_port)

    return redis_client


class SyncStatusKey(object):
    def __init__(self, account_id, folder_id):
        self.account_id = account_id
        self.folder_id = folder_id
        self.key = '{} {}'.format(self.account_id, self.folder_id)

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
        account_id, folder_id = map(int, string_key.split())
        return cls(account_id, folder_id)


class SyncStatus(object):
    def __init__(self, account_id, folder_id, delta=timedelta(seconds=60)):
        self.key = SyncStatusKey(account_id, folder_id)
        self.timestamp = None
        self.delta = delta
        self.redis_client = _get_redis_client()
        self.log = log.new(component='syncstatus', key=self.key)

    def publish(self, force=False, **kwargs):
        timestamp = datetime.utcnow()
        if timestamp - (self.timestamp or datetime.min) < self.delta and \
                not force:
            return
        value = dict(timestamp=timestamp)
        value.update(kwargs or {})
        try:
            self.redis_client.hmset(self.key, value)
            self.timestamp = timestamp
        except Exception:
            log.error('Error while publishing status on Redis', exc_info=True)
