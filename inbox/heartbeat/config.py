from collections import namedtuple
from datetime import timedelta
from redis import StrictRedis

from inbox.config import config

STATUS_DATABASE = 1
REPORT_DATABASE = 2

BASE_ALIVE_THRESHOLD = 480
CONTACTS_ALIVE_THRESHOLD = 480
EVENTS_ALIVE_THRESHOLD = 480
EAS_THROTTLED_ALIVE_THRESHOLD = BASE_ALIVE_THRESHOLD + 120
EAS_PING_ALIVE_THRESHOLD = 780


AliveThresholds = namedtuple('AliveThresholds',
                             ['base',
                              'contacts',
                              'events',
                              'eas_throttled',
                              'eas_ping'])


alive_thresholds = None


def get_alive_thresholds():
    global alive_thresholds
    if not alive_thresholds:
        base = int(config.get_required('BASE_ALIVE_THRESHOLD'))
        contacts = int(config.get_required('CONTACTS_ALIVE_THRESHOLD'))
        events = int(config.get_required('EVENTS_ALIVE_THRESHOLD'))
        eas_throttled = int(config.get_required('EAS_ALIVE_THRESHOLD'))
        eas_ping = int(config.get_required('EAS_ALIVE_THRESHOLD'))

        alive_thresholds = AliveThresholds(
            base=timedelta(seconds=base),
            contacts=timedelta(seconds=contacts),
            events=timedelta(seconds=events),
            eas_throttled=timedelta(seconds=eas_throttled),
            eas_ping=timedelta(seconds=eas_ping))

    return alive_thresholds


def _get_alive_thresholds():
    return AliveThresholds(
        base=timedelta(seconds=BASE_ALIVE_THRESHOLD),
        contacts=timedelta(seconds=CONTACTS_ALIVE_THRESHOLD),
        events=timedelta(seconds=EVENTS_ALIVE_THRESHOLD),
        eas_throttled=timedelta(seconds=EAS_THROTTLED_ALIVE_THRESHOLD),
        eas_ping=timedelta(seconds=EAS_PING_ALIVE_THRESHOLD))


redis_client = None


def get_redis_client(db):
    global redis_client
    if redis_client is None:
        host = str(config.get_required('REDIS_HOSTNAME'))
        port = int(config.get_required('REDIS_PORT'))

        redis_client = StrictRedis(host, port, db)

    return redis_client


def _get_redis_client(host, port, db):
    return StrictRedis(host, port, db)
