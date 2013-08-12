import crispin
import uuid

import logging as log
import datetime
import traceback
import google_oauth
from models import db_session, User, UserSession

# Memory cache for currently open crispin instances
email_address_to_crispins = {}



def log_ignored(exc):
    log.error('Ignoring error: %s\nOuter stack:\n%s%s'
              % (exc, ''.join(traceback.format_stack()[:-2]), traceback.format_exc(exc)))



def create_session(email_address):
    new_session = UserSession()
    new_session.email_address = email_address
    new_session.session_token = str(uuid.uuid1())
    db_session.add(new_session)
    db_session.commit()
    return new_session



def get_session(session_token):
    session_obj = db_session.query(UserSession).filter_by(session_token=session_token).first()
    if not session_obj:
        log.error("No record for session with token: %s" % session_token)
    return session_obj




def store_access_token(access_token_dict):
    new_user = User()
    # new_user.name = None
    new_user.g_token_issued_to = access_token_dict['issued_to']
    new_user.g_user_id = access_token_dict['user_id']
    new_user.g_access_token = access_token_dict['access_token']
    new_user.g_id_token = access_token_dict['id_token']
    new_user.g_expires_in = access_token_dict['expires_in']
    new_user.g_access_type = access_token_dict['access_type']
    new_user.g_token_type = access_token_dict['token_type']
    new_user.g_audience = access_token_dict['audience']
    new_user.g_scope = access_token_dict['scope']
    new_user.g_email = access_token_dict['email']
    new_user.g_refresh_token = access_token_dict['refresh_token']
    new_user.g_verified_email = access_token_dict['verified_email']
    new_user.date = datetime.datetime.utcnow()  # Used to verify key lifespan

    db_session.add(new_user)
    db_session.commit()

    # Close old crispin connection
    if new_user.g_email in email_address_to_crispins:
        old_crispin = email_address_to_crispins[new_user.g_email]
        old_crispin.stop()
        del email_address_to_crispins[new_user.g_email]

    log.info("Stored new user object %s" % new_user)
    return new_user



def get_user(email_address, callback=None):

    user_obj = db_session.query(User).filter_by(g_email=email_address).first()
    if not user_obj:
        log.error("Should already have a user object...")
        return None


    issued_date = user_obj.date
    expires_seconds = user_obj.g_expires_in

    # TODO check with expire date first
    expire_date = issued_date + datetime.timedelta(seconds=expires_seconds)

    is_valid = google_oauth.validate_token(user_obj.g_access_token)

    # TODO refresh tokens based on date instead of checking?
    # if not is_valid or expire_date > datetime.datetime.utcnow():
    if not is_valid:
        log.error("Need to update access token!")

        refresh_token = user_obj.g_refresh_token

        log.error("Getting new access token...")
        response = google_oauth.get_new_token(refresh_token)  # TOFIX blocks

        # TODO handling errors here for when oauth has been revoked
        if 'error' in response:
            log.error(response['error'])
            if response['error'] == 'invalid_grant':
                # Means we need to reset the entire oauth process.
                log.error("Refresh token is invalid.")
            return None

        # TODO Verify it and make sure it's valid.
        assert 'access_token' in response
        user_obj = store_access_token(response)
        log.info("Updated token for user %s" % user_obj.g_email)

    log.info("Returing user object: %s" % user_obj)
    return user_obj



def get_crispin_from_session(session_token):
    """ Get the running crispin instance, or make a new one """
    s = get_session(session_token)
    return get_crispin_from_email(s.email_address)


def get_crispin_from_email(email_address):
    if email_address in email_address_to_crispins:
        return email_address_to_crispins[email_address]
    else:
        user_obj = get_user(email_address)

        crispin_client =  crispin.CrispinClient(user_obj.g_email, user_obj.g_access_token)

        email_address_to_crispins[email_address] = crispin_client
        return crispin_client


def stop_all_crispins():
    if not email_address_to_crispins: return
    for e,c in email_address_to_crispins.iteritems():
        c.stop()

