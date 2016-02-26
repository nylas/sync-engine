import sys
import time
from contextlib import contextmanager

import gevent
from sqlalchemy import event
from sqlalchemy.orm.session import Session
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.horizontal_shard import ShardedSession

from inbox.config import config
from inbox.ignition import engine_manager
from inbox.util.stats import statsd_client
from nylas.logging import get_logger, find_first_app_frame_and_name
log = get_logger()


MAX_SANE_TRX_TIME_MS = 30000


def two_phase_session(engine_map, versioned=True):
    """
    Returns a session that implements two-phase-commit.
    Parameters
    ----------
    engine_map: dict
    Mapping of Table cls instance: database engine

    versioned: bool

    """
    session = Session(binds=engine_map, twophase=True, autoflush=True,
                      autocommit=False)
    if versioned:
        session = configure_versioning(session)
        # TODO[k]: Metrics for transaction latencies!
    return session


def new_session(engine, versioned=True, explicit_begin=False):
    """Returns a session bound to the given engine."""
    session = Session(bind=engine, autoflush=True, autocommit=False)

    if versioned:
        configure_versioning(session)

        # Make statsd calls for transaction times
        transaction_start_map = {}
        frame, modname = find_first_app_frame_and_name(
            ignores=['sqlalchemy', 'inbox.models.session', 'nylas.logging',
                     'contextlib'])
        funcname = frame.f_code.co_name
        modname = modname.replace(".", "-")
        metric_name = 'db.{}.{}.{}'.format(engine.url.database, modname,
                                           funcname)

        @event.listens_for(session, 'after_begin')
        def after_begin(session, transaction, connection):
            if explicit_begin:
                connection.execute('BEGIN')
            # It's okay to key on the session object here, because each session
            # binds to only one engine/connection. If this changes in the
            # future such that a session may encompass multiple engines, then
            # we'll have to get more sophisticated.
            transaction_start_map[session] = time.time()

        @event.listens_for(session, 'after_commit')
        @event.listens_for(session, 'after_rollback')
        def end(session):
            start_time = transaction_start_map.get(session)
            if not start_time:
                return

            del transaction_start_map[session]

            t = time.time()
            latency = int((t - start_time) * 1000)
            statsd_client.timing(metric_name, latency)
            statsd_client.incr(metric_name)
            if latency > MAX_SANE_TRX_TIME_MS:
                log.warning('Long transaction', latency=latency,
                            modname=modname, funcname=funcname)

    return session


def configure_versioning(session):
    from inbox.models.transaction import (create_revisions, propagate_changes,
                                          increment_versions)

    @event.listens_for(session, 'before_flush')
    def before_flush(session, flush_context, instances):
        propagate_changes(session)
        increment_versions(session)

    @event.listens_for(session, 'after_flush')
    def after_flush(session, flush_context):
        """
        Hook to log revision snapshots. Must be post-flush in order to
        grab object IDs on new objects.

        """
        create_revisions(session)

    return session


@contextmanager
def session_scope(id_, versioned=True, explicit_begin=False):
    """
    Provide a transactional scope around a series of operations.

    Takes care of rolling back failed transactions and closing the session
    when it goes out of scope.

    Note that sqlalchemy automatically starts a new database transaction when
    the session is created, and restarts a new transaction after every commit()
    on the session. Your database backend's transaction semantics are important
    here when reasoning about concurrency.

    Parameters
    ----------
    versioned : bool
        Do you want to enable the transaction log?
    explicit_begin: bool
        If True, issue an explicit BEGIN statement instead of relying on
        implicit transactional semantics.

    Yields
    ------
    Session
        The created session.

    """
    engine = engine_manager.get_for_id(id_)
    session = new_session(engine, versioned)

    try:
        if config.get('LOG_DB_SESSIONS'):
            start_time = time.time()
            calling_frame = sys._getframe().f_back.f_back
            call_loc = '{}:{}'.format(calling_frame.f_globals.get('__name__'),
                                      calling_frame.f_lineno)
            logger = log.bind(engine_id=id(engine),
                              session_id=id(session), call_loc=call_loc)
            logger.info('creating db_session',
                        sessions_used=engine.pool.checkedout())
        yield session
        session.commit()
    except (gevent.GreenletExit, gevent.Timeout) as exc:
        log.info('Invalidating connection on gevent exception', exc_info=True)
        session.invalidate()
    except BaseException as exc:
        try:
            session.rollback()
            raise
        except OperationalError:
            log.warn('Encountered OperationalError on rollback',
                     original_exception=type(exc))
            raise exc
    finally:
        if config.get('LOG_DB_SESSIONS'):
            lifetime = time.time() - start_time
            logger.info('closing db_session', lifetime=lifetime,
                        sessions_used=engine.pool.checkedout())
        session.close()


@contextmanager
def session_scope_by_shard_id(shard_id, versioned=True):
    key = shard_id << 48

    with session_scope(key, versioned) as db_session:
        yield db_session


# GLOBAL (cross-shard) queries. USE WITH CAUTION.


def shard_chooser(mapper, instance, clause=None):
    return str(engine_manager.shard_key_for_id(instance.id))


def id_chooser(query, ident):
    # STOPSHIP(emfree): is ident a tuple here???
    # TODO[k]: What if len(list) > 1?
    if isinstance(ident, list) and len(ident) == 1:
        ident = ident[0]
    return [str(engine_manager.shard_key_for_id(ident))]


def query_chooser(query):
    return [str(k) for k in engine_manager.engines]


@contextmanager
def global_session_scope():
    shards = {str(k): v for k, v in engine_manager.engines.items()}
    session = ShardedSession(
        shard_chooser=shard_chooser,
        id_chooser=id_chooser,
        query_chooser=query_chooser,
        shards=shards)
    # STOPSHIP(emfree): need instrumentation and proper exception handling
    # here.
    try:
        yield session
    finally:
        session.close()
