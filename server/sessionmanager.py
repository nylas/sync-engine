import crispin
import uuid

import logging as log
import datetime
import traceback
import google_oauth
from models import db_session, User, UserSession, Namespace, Credentials

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
                ).filter_by(token=session_token).join(User, Namespace).one()
    except sqlalchemy.orm.exc.NoResultFound:
        log.error("No record for session with token: %s" % session_token)
        return None
    except:
        raise

def make_namespace(access_token_dict):
    try:
        namespace = db_session.query(Namespace).filter_by(
                email_address=access_token_dict['email']).join(
                        Credentials).one()
        user = db_session.query(User).filter_by(
                root_namespace=namespace)
    except sqlalchemy.orm.exc.NoResultFound:
        namespace = Namespace(credentials=Credentials())
        user = User(root_namespace=namespace)
    namespace.email_address = access_token_dict['email']
    namespace.credentials.o_token_issued_to = access_token_dict['issued_to']
    namespace.credentials.o_user_id = access_token_dict['user_id']
    namespace.credentials.o_access_token = access_token_dict['access_token']
    namespace.credentials.o_id_token = access_token_dict['id_token']
    namespace.credentials.o_expires_in = access_token_dict['expires_in']
    namespace.credentials.o_access_type = access_token_dict['access_type']
    namespace.credentials.o_token_type = access_token_dict['token_type']
    namespace.credentials.o_audience = access_token_dict['audience']
    namespace.credentials.o_scope = access_token_dict['scope']
    namespace.credentials.o_email = access_token_dict['email']
    namespace.credentials.o_refresh_token = access_token_dict['refresh_token']
    namespace.credentials.o_verified_email = access_token_dict['verified_email']
    namespace.credentials.date = datetime.datetime.utcnow()

    db_session.add(namespace)
    db_session.add(user)
    db_session.commit()
    log.info("Stored new user {0} with namespace {1}".format(namespace.id, user.id))
    return namespace, user

def get_namespace(email_address, callback=None):
    namespace = db_session.query(Namespace).filter_by(
            email_address=email_address).join('credentials').one()
    return verify_namespace(namespace)

def verify_namespace(namespace):
    # issued_date = credentials.date
    # expires_seconds = credentials.o_expires_in
    credentials = namespace.credentials

    # TODO check with expire date first
    # expire_date = issued_date + datetime.timedelta(seconds=expires_seconds)

    is_valid = google_oauth.validate_token(credentials.o_access_token)

    # TODO refresh tokens based on date instead of checking?
    # if not is_valid or expire_date > datetime.datetime.utcnow():
    if not is_valid:
        log.error("Need to update access token!")

        refresh_token = credentials.o_refresh_token

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
        namespace = make_namespace(response)
        log.info("Updated token for namespace {0}" % namespace.email_address)

    return namespace

def get_crispin_from_session(session_token):
    """ Get the running crispin instance, or make a new one """
    s = get_session(session_token)
    return get_crispin_from_email(s.email_address)

def get_crispin_from_email(email_address, initial=False, dummy=False):
    cls = crispin.DummyCrispinClient if dummy else crispin.CrispinClient
    if email_address in email_address_to_crispins:
        return email_address_to_crispins[email_address]
    else:
        namespace = get_namespace(email_address)
        assert namespace is not None
        crispin_client =  cls(namespace)

        assert 'X-GM-EXT-1' in crispin_client.imap_server.capabilities(), "This must not be Gmail..."

        email_address_to_crispins[email_address] = crispin_client
        return crispin_client

def stop_all_crispins():
    if not email_address_to_crispins:
        return
    for e,c in email_address_to_crispins.iteritems():
        c.stop()

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
