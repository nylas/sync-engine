from collections import namedtuple
from datetime import timedelta
from redis import StrictRedis

from inbox.config import ConfigError, config

STATUS_DATABASE = 1
REPORT_DATABASE = 2

BASE_ALIVE_THRESHOLD = 180
CONTACTS_ALIVE_THRESHOLD = 420
EVENTS_ALIVE_THRESHOLD = 420
EAS_ALIVE_THRESHOLD = 420


AliveThresholds = namedtuple('AliveThresholds',
                             ['base', 'contacts', 'events', 'eas'])


alive_thresholds = None


def get_alive_thresholds():
    global alive_thresholds
    if not alive_thresholds:
        try:
            # try the new configuration
            base = int(config.get_required('BASE_ALIVE_THRESHOLD'))
            contacts = int(config.get_required('CONTACTS_ALIVE_THRESHOLD'))
            events = int(config.get_required('EVENTS_ALIVE_THRESHOLD'))
            eas = int(config.get_required('EAS_ALIVE_THRESHOLD'))
        except ConfigError:
            # try the old configuration
            base = int(config.get_required('ALIVE_THRESHOLD'))
            contacts = int(config.get_required('ALIVE_THRESHOLD_CONTACTS'))
            events = int(config.get_required('ALIVE_THRESHOLD_EVENTS'))
            eas = int(config.get_required('ALIVE_THRESHOLD_EAS'))

        alive_thresholds = AliveThresholds(
            base=timedelta(seconds=base),
            contacts=timedelta(seconds=contacts),
            events=timedelta(seconds=events),
            eas=timedelta(seconds=eas))

    return alive_thresholds


def _get_alive_thresholds():
    return AliveThresholds(
        base=timedelta(seconds=BASE_ALIVE_THRESHOLD),
        contacts=timedelta(seconds=CONTACTS_ALIVE_THRESHOLD),
        events=timedelta(seconds=EVENTS_ALIVE_THRESHOLD),
        eas=timedelta(seconds=EAS_ALIVE_THRESHOLD))


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
