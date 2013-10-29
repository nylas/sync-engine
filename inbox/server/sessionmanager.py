import crispin
import uuid

# XXX for crispin, we probably want to do per-user logging instead
from .log import get_logger
log = get_logger()

import datetime
import traceback
import google_oauth
from models import db_session, User, UserSession, Namespace, IMAPAccount

import sqlalchemy.orm.exc

# Memory cache for currently open crispin instances
email_address_to_crispins = {}

def log_ignored(exc):
    log.error('Ignoring error: %s\nOuter stack:\n%s%s'
              % (exc, ''.join(traceback.format_stack()[:-2]), traceback.format_exc(exc)))

def create_session(user):
    new_session = UserSession(user=user, token=str(uuid.uuid1()))
    db_session.add(new_session)
    db_session.commit()
    log.info("Created new session with token: {0}".format(
        str(new_session.token)))
    return new_session

def get_session(session_token):
    # XXX doesn't deal with multiple sessions
    try:
        return db_session.query(UserSession
                ).filter_by(token=session_token).join(User, IMAPAccount, Namespace
                        ).one()
    except sqlalchemy.orm.exc.NoResultFound:
        log.error("No record for session with token: %s" % session_token)
        return None
    except:
        raise

def make_account(access_token_dict):
    try:
        account = db_session.query(IMAPAccount).filter_by(
                email_address=access_token_dict['email']).one()
    except sqlalchemy.orm.exc.NoResultFound:
        user = User()
        namespace = Namespace()
        account = IMAPAccount(user=user, namespace=namespace)
    account.email_address = access_token_dict['email']
    account.o_token_issued_to = access_token_dict['issued_to']
    account.o_user_id = access_token_dict['user_id']
    account.o_access_token = access_token_dict['access_token']
    account.o_id_token = access_token_dict['id_token']
    account.o_expires_in = access_token_dict['expires_in']
    account.o_access_type = access_token_dict['access_type']
    account.o_token_type = access_token_dict['token_type']
    account.o_audience = access_token_dict['audience']
    account.o_scope = access_token_dict['scope']
    account.o_email = access_token_dict['email']
    account.o_refresh_token = access_token_dict['refresh_token']
    account.o_verified_email = access_token_dict['verified_email']
    account.date = datetime.datetime.utcnow()

    db_session.add(account)
    db_session.commit()
    log.info("Stored new account {0}".format(account.email_address))
    return account

def get_account(email_address, callback=None):
    account = db_session.query(IMAPAccount).filter(
            IMAPAccount.email_address==email_address).join(Namespace).one()
    return verify_imap_account(account)

def verify_imap_account(account):
    # issued_date = credentials.date
    # expires_seconds = credentials.o_expires_in

    # TODO check with expire date first
    # expire_date = issued_date + datetime.timedelta(seconds=expires_seconds)

    is_valid = google_oauth.validate_token(account.o_access_token)

    # TODO refresh tokens based on date instead of checking?
    # if not is_valid or expire_date > datetime.datetime.utcnow():
    if not is_valid:
        log.error("Need to update access token!")

        refresh_token = account.o_refresh_token

        log.error("Getting new access token...")
        response = google_oauth.get_new_token(refresh_token)  # TOFIX blocks
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
        account = make_account(response)
        log.info("Updated token for imap account {0}".format(account.email_address))

    return account

def get_crispin_from_session(session_token):
    """ Get the running crispin instance, or make a new one """
    s = get_session(session_token)
    return get_crispin_from_email(s.email_address)

def get_crispin_from_email(email_address, initial=False, dummy=False):
    cls = crispin.DummyCrispinClient if dummy else crispin.CrispinClient
    if email_address in email_address_to_crispins:
        return email_address_to_crispins[email_address]
    else:
        account = get_account(email_address)
        assert account is not None
        crispin_client =  cls(account)

        assert 'X-GM-EXT-1' in crispin_client.imap_server.capabilities(), "This must not be Gmail..."

        email_address_to_crispins[email_address] = crispin_client
        return crispin_client

def stop_all_crispins():
    if not email_address_to_crispins:
        return
    for e,c in email_address_to_crispins.iteritems():
        c.stop()

