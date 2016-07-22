"""This module contains code for managing Redis-backed account sync allocation.
Structurally, that works like this:

                                Redis list                Redis hash
                             (acct ids to be        (acct ids -> proc ids)
                                 synced)            +---------+---------+
  +------------+             +----+----+----+       |    33   |   42    |
  |  mysql db  | -------- -> | 44 | 37 | 22 | ----> +---------+---------+
  +------------+     |       +----+----+----+   |   | hostA:3 | hostB:7 |
                     |                          |   +---------+---------+
                QueuePopulator             SyncService


The QueuePopulator is responsible for pulling all syncable account ids from the
core mailsync MySQL database. It populates a Redis queue with any account ids
not currently being synced. Individual sync processes pull account ids off of
this queue, and claim ownership by updating a Redis hash that maps account
ids to process identifiers. We use a bit of Redis Lua scripting to ensure that
this happens atomically.
"""

import gevent
import itertools
from inbox.config import config
from inbox.ignition import engine_manager
from inbox.models.session import session_scope_by_shard_id
from inbox.models import Account
from inbox.util.concurrency import retry_with_logging
from inbox.util.stats import statsd_client
from nylas.logging import get_logger
from redis import StrictRedis
log = get_logger()

SOCKET_CONNECT_TIMEOUT = 5
SOCKET_TIMEOUT = 5


class QueueClient(object):
    """Interface to a Redis queue/hashmap combo for managing account sync
    allocation.
    """

    # Lua scripts for atomic assignment and conflict-free unassignment.
    ASSIGN = '''
    local k = redis.call('RPOP', KEYS[1])
    if k then
        local s = redis.call('HSETNX', KEYS[2], k, ARGV[1])
        if s then
            return k
        end
    end'''

    TRANSFER_ACCOUNT = '''
    redis.call('HDEL', KEYS[3], KEYS[2])
    redis.call('HSETNX', KEYS[1], KEYS[2], ARGV[1])
    '''

    UNASSIGN = '''
    if redis.call('HGET', KEYS[1], KEYS[2]) == ARGV[1] then
        return redis.call('HDEL', KEYS[1], KEYS[2])
    else
        return 0
    end
    '''

    def __init__(self, zone):
        self.zone = zone
        redis_host = config['ACCOUNT_QUEUE_REDIS_HOSTNAME']
        redis_db = config['ACCOUNT_QUEUE_REDIS_DB']
        self.redis = StrictRedis(host=redis_host, db=redis_db,
                                 socket_connect_timeout=SOCKET_CONNECT_TIMEOUT,
                                 socket_timeout=SOCKET_TIMEOUT)

    def all(self):
        """
        Returns all keys being tracked (either pending in the queue, or
        already assigned).

        """
        p = self.redis.pipeline(transaction=True)
        p.hgetall(self._hash)
        p.lrange(self._queue, 0, -1)
        unassigned, assigned = p.execute()
        return {int(k) for k in itertools.chain(unassigned, assigned)}

    def assigned(self):
        """
        Returns a dictionary of all currently assigned key/value pairs (keys
        are coerced to integers).
        """
        return {int(k): v for k, v in self.redis.hgetall(self._hash).items()}

    def enqueue(self, key):
        """
        Adds a new key onto the pending queue.
        """
        self.redis.lpush(self._queue, key)

    def claim_next(self, value):
        """
        Pulls the next key off of the pending queue (if any exists), and sets
        it to `value` in the hash. Returns None if the queue is empty or if the
        key is already present in the hash; otherwise returns the key.
        """
        s = self.redis.register_script(self.ASSIGN)
        return s(keys=[self._queue, self._hash], args=[value])

    def transfer_account(self, key, value, zone):
        """
        Transfer the account_id from one sync host to another
        """

        # Other hash exists in the case that the
        # two instances are not in the same zone
        other_hash = 'assigned_{}'.format(zone)

        s = self.redis.register_script(self.TRANSFER_ACCOUNT)
        return s(keys=[self._hash, key, other_hash], args=[value])

    def unassign(self, key, value):
        """
        Removes `key` from the hash, if and only if it is present and set to
        `value` (to prevent removing a key actually assigned to someone else).
        """
        s = self.redis.register_script(self.UNASSIGN)
        return s(keys=[self._hash, key], args=[value])

    def qsize(self):
        """
        Returns current length of the queue.
        """
        return self.redis.llen(self._queue)

    @property
    def _queue(self):
        return 'unassigned_{}'.format(self.zone)

    @property
    def _hash(self):
        return 'assigned_{}'.format(self.zone)


class QueuePopulator(object):
    """
    Polls the database for account ids to sync and queues them. Run one of
    these per zone.
    """
    def __init__(self, zone, poll_interval=1):
        self.zone = zone
        self.poll_interval = poll_interval
        self.queue_client = QueueClient(zone)
        self.shards = []
        for database in config['DATABASE_HOSTS']:
            if database.get('ZONE') == self.zone:
                shard_ids = [shard['ID'] for shard in database['SHARDS']]
                self.shards.extend(shard_id for shard_id in shard_ids
                                   if shard_id in engine_manager.engines)

    def run(self):
        return retry_with_logging(self._run_impl)

    def _run_impl(self):
        log.info('Queueing accounts', zone=self.zone, shards=self.shards)
        while True:
            self.enqueue_new_accounts()
            self.unassign_disabled_accounts()
            statsd_client.gauge('syncqueue.queue.{}.length'.format(self.zone),
                                self.queue_client.qsize())
            statsd_client.incr('syncqueue.service.{}.heartbeat'.
                               format(self.zone))
            gevent.sleep(self.poll_interval)

    def enqueue_new_accounts(self):
        """
        Finds any account ids that should sync, but are not currently being
        tracked by the QueueClient. Enqueue them. (Note: it's okay to enqueue
        the same id twice. QueueClient.claim_next will identify and discard
        duplicates.)
        """
        new_accounts = self.runnable_accounts() - self.queue_client.all()
        for account_id in new_accounts:
            log.info('Enqueuing new account', account_id=account_id)
            self.queue_client.enqueue(account_id)

    def unassign_disabled_accounts(self):
        runnable_accounts = self.runnable_accounts()
        disabled_accounts = {
            k: v for k, v in self.queue_client.assigned().items()
            if k not in runnable_accounts
        }
        for account_id, sync_host in disabled_accounts.items():
            log.info('Removing disabled account', account_id=account_id)
            self.queue_client.unassign(account_id, sync_host)

    def runnable_accounts(self):
        accounts = set()
        for key in self.shards:
            with session_scope_by_shard_id(key) as db_session:
                accounts.update(
                    id_ for id_, in db_session.query(Account.id).filter(
                        Account.sync_should_run))
        return accounts
