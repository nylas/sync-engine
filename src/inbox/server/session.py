import traceback, uuid
import sqlalchemy.orm.exc

from inbox.server.log import get_logger
log = get_logger()

from inbox.server.models.tables import (User, UserSession, Namespace,
    ImapAccount)


def log_ignored(exc):
    log.error('Ignoring error: {0}\nOuter stack:\n{1}{2}'.format(exc,
        ''.join(traceback.format_stack()[:-2]), traceback.format_exc(exc)))


def create_session(db_session, user):
    new_session = UserSession(user=user, token=str(uuid.uuid1()))
    db_session.add(new_session)
    db_session.commit()
    log.info('Created new session with token: {0}'.format(new_session.token))
    return new_session


def get_session(db_session, session_token):
    # XXX doesn't deal with multiple sessions
    try:
        return db_session.query(UserSession).filter_by(
            token=session_token).join(User, ImapAccount, Namespace).one()
    except sqlalchemy.orm.exc.NoResultFound:
        log.error('No record for session with token: {0}'.format(
            session_token))
        return None
    except:
        raise
