import json
from redis import StrictRedis

from inbox.config import config
from nylas.logging import get_logger
log = get_logger()

SOCKET_CONNECT_TIMEOUT = 5
SOCKET_TIMEOUT = 30


def _get_redis_client(host=None, port=6379, db=1):
    return StrictRedis(host=host,
                       port=port,
                       db=db,
                       socket_connect_timeout=SOCKET_CONNECT_TIMEOUT,
                       socket_timeout=SOCKET_TIMEOUT)


class EventQueue(object):
    """Simple queue that clients can listen to and wait to be notified of some
    event that they're interested in.
    """
    def __init__(self, queue_name, redis=None):
        self.redis = redis
        if self.redis is None:
            redis_host = config['EVENT_QUEUE_REDIS_HOSTNAME']
            redis_db = config['EVENT_QUEUE_REDIS_DB']
            self.redis = _get_redis_client(host=redis_host, db=redis_db)
        self.queue_name = queue_name

    def receive_event(self, timeout=0):
        result = None
        if timeout is None:
            result = self.redis.lpop(self.queue_name)
        else:
            result = self.redis.blpop([self.queue_name], timeout=timeout)

        if result is None:
            return None
        queue_name, event_data = (self.queue_name, result) if timeout is None else result
        try:
            event = json.loads(event_data)
            event['queue_name'] = queue_name
            return event
        except Exception as e:
            log.error('Failed to load event data from queue', error=e, event_data=event_data)
            return None

    def send_event(self, event_data):
        event_data.pop('queue_name', None)
        self.redis.rpush(self.queue_name, json.dumps(event_data))


class EventQueueGroup(object):
    """Group of queues that can all be simultaneously watched for new events."""
    def __init__(self, queues):
        self.queues = queues
        self.redis = None
        if len(self.queues) > 0:
            self.redis = self.queues[0].redis

    def receive_event(self, timeout=0):
        result = self.redis.blpop([q.queue_name for q in self.queues], timeout=timeout)
        if result is None:
            return None
        queue_name, event_data = result
        try:
            event = json.loads(event_data)
            event['queue_name'] = queue_name
            return event
        except Exception as e:
            log.error('Failed to load event data from queue', error=e, event_data=event_data)
            return None
