from redis import StrictRedis

from inbox.config import config

STATUS_DATABASE = 1
REPORT_DATABASE = 2

ALIVE_EXPIRY = int(config.get('BASE_ALIVE_THRESHOLD', 480))

CONTACTS_FOLDER_ID = '-1'
EVENTS_FOLDER_ID = '-2'


def get_redis_client(host=None, port=6379, db=STATUS_DATABASE):
    if not host:
        host = str(config.get_required('REDIS_HOSTNAME'))
        port = int(config.get_required('REDIS_PORT'))
    return StrictRedis(host, port, db)
