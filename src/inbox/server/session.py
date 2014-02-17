import uuid
import datetime
import traceback
import sys

import sqlalchemy.orm.exc

from inbox.util.url import provider_from_address, NotSupportedError

from .log import get_logger
log = get_logger()

from . import oauth
from .models.tables import User, UserSession, Namespace, ImapAccount

IMAP_HOSTS = { 'Gmail': 'imap.gmail.com',
                'Yahoo': 'imap.mail.yahoo.com' }

HANDLERS = {
    'AUTH': {
        'Gmail': oauth.oauth,
        'Yahoo': oauth.password_auth
    }
}

def log_ignored(exc):
    log.error('Ignoring error: %s\nOuter stack:\n%s%s'
              % (exc, ''.join(traceback.format_stack()[:-2]), traceback.format_exc(exc)))

def create_session(db_session, user):
    new_session = UserSession(user=user, token=str(uuid.uuid1()))
    db_session.add(new_session)
    db_session.commit()
    log.info("Created new session with token: {0}".format(
        str(new_session.token)))
    return new_session

def get_session(db_session, session_token):
    # XXX doesn't deal with multiple sessions
    try:
        return db_session.query(UserSession
                ).filter_by(token=session_token).join(User, ImapAccount, Namespace
                        ).one()
    except sqlalchemy.orm.exc.NoResultFound:
        log.error("No record for session with token: %s" % session_token)
        return None
    except:
        raise

# TODO[kavya]: Auth's error handling
def auth_account(email_address):
    provider = provider_from_address(email_address)
    handler = HANDLERS['AUTH'].get(provider)

    if handler is None:
        # TODO: Error handling/propogation to caller here?
        raise NotSupportedError('Inbox currently only supports Gmail and Yahoo.')
        sys.exit(1)

    response = handler(email_address)
    return response

def make_account(db_session, email_address, response):
    try:
        account = db_session.query(ImapAccount).filter_by(
                email_address=email_address).one()
    except sqlalchemy.orm.exc.NoResultFound:
        user = User()
        namespace = Namespace()
        account = ImapAccount(user=user, namespace=namespace)

    provider = provider_from_address(email_address)

    if (provider == 'Gmail'):
        account.provider = 'Gmail'
        account.imap_host = IMAP_HOSTS['Gmail']
        account.email_address = response['email']
        account.o_token_issued_to = response['issued_to']
        account.o_user_id = response['user_id']
        account.o_access_token = response['access_token']
        account.o_id_token = response['id_token']
        account.o_expires_in = response['expires_in']
        account.o_access_type = response['access_type']
        account.o_token_type = response['token_type']
        account.o_audience = response['audience']
        account.o_scope = response['scope']
        account.o_email = response['email']
        account.o_refresh_token = response['refresh_token']
        account.o_verified_email = response['verified_email']
        account.date = datetime.datetime.utcnow()

    elif (provider == 'Yahoo'):
        account.provider = 'Yahoo'
        account.imap_host = IMAP_HOSTS['Yahoo']
        account.email_address = response['email']
        account.password = response['password']
        account.date = datetime.datetime.utcnow()

    else:
        # TODO[kavya]: Error handling/propogation to caller here?
        raise NotSupportedError('Inbox currently only supports Gmail and Yahoo.')
        sys.exit(1)

    return account

def verify_account(db_session, account):
    from inbox.server.pool import verify_gmail_account, verify_yahoo_account
    HANDLERS['VERIFY'] = {
        'Gmail': verify_gmail_account,
        'Yahoo': verify_yahoo_account
    }

    provider = provider_from_address(account.email_address)
    handler = HANDLERS['VERIFY'].get(provider)

    if handler is None:
         # TODO[kavya]: Bubbled up to caller here, check if okay
        raise NotSupportedError('Inbox currently only supports Gmail and Yahoo.')

    handler(account)
    commit_account(db_session, account)

    return account

def commit_account(db_session, account):
    db_session.add(account)
    db_session.commit()

    log.info("Stored new account {0}".format(account.email_address))

def get_account(db_session, email_address, callback=None):
    account = db_session.query(ImapAccount).filter(
            ImapAccount.email_address==email_address).join(Namespace).one()
    return verify_imap_account(db_session, account)

def verify_imap_account(db_session, account):
    # issued_date = credentials.date
    # expires_seconds = credentials.o_expires_in

    # TODO check with expire date first
    # expire_date = issued_date + datetime.timedelta(seconds=expires_seconds)

    is_valid = oauth.validate_token(account.o_access_token)

    # TODO refresh tokens based on date instead of checking?
    # if not is_valid or expire_date > datetime.datetime.utcnow():
    if not is_valid:
        log.error("Need to update access token!")

        refresh_token = account.o_refresh_token

        log.error("Getting new access token...")
        response = oauth.get_new_token(refresh_token)  # TOFIX blocks
        response['refresh_token'] = refresh_token  # Propogate it through

        # TODO handling errors here for when oauth has been revoked
        if 'error' in response:
            log.error(response['error'])
            if response['error'] == 'invalid_grant':
                # Means we need to reset the entire oauth process.
                log.error("Refresh token is invalid.")
            return None

        # TODO Verify it and make sure it's valid.
        assert 'access_token' in response
        account = make_account(db_session, response)
        log.info("Updated token for imap account {0}".format(account.email_address))

    return account
