import gevent
import json
import time

from inbox.models.account import Account
from inbox.models.session import session_scope
from inbox.scheduling import event_queue
from inbox.util.concurrency import retry_with_logging
from inbox.util.stats import statsd_client

from nylas.logging import get_logger
log = get_logger()


DEFERRED_ACCOUNT_MIGRATION_COUNTER = 'sync:deferred_account_migration_counter'
DEFERRED_ACCOUNT_MIGRATION_PQUEUE = 'sync:deferred_account_migration_pqueue'
DEFERRED_ACCOUNT_MIGRATION_EVENT_QUEUE = 'sync:deferred_account_migration_event_queue'
DEFERRED_ACCOUNT_MIGRATION_OBJ = 'sync:deferred_account_migration_objs:{}'
DEFERRED_ACCOUNT_MIGRATION_OBJ_TTL = 60 * 60 * 24 * 7   # 1 week


class DeferredAccountMigration(object):
    _redis_fields = ['deadline', 'account_id', 'desired_host', 'id']

    def __init__(self, deadline, account_id, desired_host, id=None):
        self.deadline = float(deadline)
        self.account_id = int(account_id)
        self.desired_host = str(desired_host)
        self.id = None if id is None else int(id)

    def execute(self, client):
        with session_scope(self.account_id) as db_session:
            account = db_session.query(Account).get(self.account_id)
            if account is None:
                log.warning('Account not found when trying to execute DeferredAccountMigration', account_id=self.account_id)
                return
            account.desired_sync_host = self.desired_host
            db_session.commit()
        self.save(client)

    def save(self, client):
        if self.id is None:
            self.id = client.incr(DEFERRED_ACCOUNT_MIGRATION_COUNTER)
        p = client.pipeline()
        key = DEFERRED_ACCOUNT_MIGRATION_OBJ.format(self.id)
        p.hmset(key, dict((field, getattr(self, field)) for field in self.__class__._redis_fields))
        p.expire(key, DEFERRED_ACCOUNT_MIGRATION_OBJ_TTL)
        p.zadd(DEFERRED_ACCOUNT_MIGRATION_PQUEUE, self.deadline, self.id)
        p.rpush(DEFERRED_ACCOUNT_MIGRATION_EVENT_QUEUE, json.dumps({'id': self.id}))
        p.execute()

    @classmethod
    def try_load(cls, client, id):
        values = client.hmget(DEFERRED_ACCOUNT_MIGRATION_OBJ.format(id), cls._redis_fields)
        if values is None:
            return None
        return DeferredAccountMigration(*values)


class DeferredAccountMigrationExecutor(gevent.Greenlet):
    def __init__(self):
        self.event_queue = event_queue.EventQueue(DEFERRED_ACCOUNT_MIGRATION_EVENT_QUEUE)
        self.redis = self.event_queue.redis
        gevent.Greenlet.__init__(self)

    def _run(self):
        while True:
            retry_with_logging(self._run_impl)

    def _run_impl(self):
        current_time = time.time()
        timeout = event_queue.SOCKET_TIMEOUT - 2    # Minus 2 to give us some leeway.
        next_deferral = self._try_get_next_deferral()
        while next_deferral is not None:
            if next_deferral.deadline >= current_time:
                timeout = int(min(max(next_deferral.deadline - current_time, 1), timeout))
                log.info('Next deferral deadline is in the future, sleeping',
                         deferral_id=next_deferral.id,
                         deadline=next_deferral.deadline,
                         desired_host=next_deferral.desired_host,
                         account_id=next_deferral.account_id,
                         timeout=timeout)
                break
            log.info('Executing deferral',
                     deferral_id=next_deferral.id,
                     deadline=next_deferral.deadline,
                     desired_host=next_deferral.desired_host,
                     account_id=next_deferral.account_id)
            next_deferral.execute(self.redis)
            self.redis.zrem(DEFERRED_ACCOUNT_MIGRATION_PQUEUE, next_deferral.id)
            next_deferral = self._try_get_next_deferral()
        self.event_queue.receive_event(timeout=timeout)
        statsd_client.incr("migrator.heartbeat")

    def _try_get_next_deferral(self):
        deferral_id = self.redis.zrange(DEFERRED_ACCOUNT_MIGRATION_PQUEUE, 0, 1)
        if not deferral_id:
            return None
        return DeferredAccountMigration.try_load(self.redis, deferral_id[0])
