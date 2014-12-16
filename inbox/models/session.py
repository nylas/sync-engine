import sys
import time
from contextlib import contextmanager

from sqlalchemy import event
from sqlalchemy.orm.session import Session

from inbox.config import config
from inbox.ignition import main_engine
from inbox.log import get_logger
log = get_logger()


cached_engine = None


def new_session(engine, versioned=True, ignore_soft_deletes=False):
    """Returns a session bound to the given engine."""
    session = Session(bind=engine, autoflush=True, autocommit=False)
    if versioned:
        from inbox.models.transaction import create_revisions

        @event.listens_for(session, 'after_flush')
        def after_flush(session, flush_context):
            """
            Hook to log revision snapshots. Must be post-flush in order to
            grab object IDs on new objects.
            """
            create_revisions(session)
    return session

# Old name for legacy code.
InboxSession = new_session


@contextmanager
def session_scope(versioned=True, ignore_soft_deletes=False):
    """ Provide a transactional scope around a series of operations.

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

    Yields
    ------
    Session
        The created session.
    """

    global cached_engine
    if cached_engine is None:
        cached_engine = main_engine()
        log.info("Don't yet have engine... creating default from ignition",
                 engine=id(cached_engine))

    session = new_session(cached_engine, versioned)

    try:
        if config.get('LOG_DB_SESSIONS'):
            start_time = time.time()
            calling_frame = sys._getframe().f_back.f_back
            call_loc = '{}:{}'.format(calling_frame.f_globals.get('__name__'),
                                      calling_frame.f_lineno)
            logger = log.bind(engine_id=id(cached_engine),
                              session_id=id(session), call_loc=call_loc)
            logger.info('creating db_session',
                        sessions_used=cached_engine.pool.checkedout())
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        if config.get('LOG_DB_SESSIONS'):
            lifetime = time.time() - start_time
            logger.info('closing db_session', lifetime=lifetime,
                        sessions_used=cached_engine.pool.checkedout())
        session.close()
