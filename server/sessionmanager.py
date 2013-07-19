import crispin
import uuid

import pymongo
# from bson.objectid import ObjectId
import logging as log
import datetime
import google_oauth
import tornado.gen
from bson.objectid import ObjectId

db = None

# Memory cache for currently open crispin instances
email_address_to_crispins = {}

def setup():
    global db
    db = pymongo.MongoClient().test
    try:
        db.create_collection('session_to_user')
        db.create_collection('user_email_to_token')
        log.info('Created collections in sessions DB"')
    except pymongo.errors.CollectionInvalid, e:
        if db.create_collection and db.create_collection:
            log.info("DB exists already.")
        else:
            log.error("Error creating sessions DB collecitons. %s" % e)


def store_session(email_address):
    global db
    session_uuid = str(uuid.uuid1())

    session = {"email_address": email_address,
               "session_uuid": session_uuid,
               "date": datetime.datetime.utcnow()
               }
    session_id = db.session_to_user.insert(session)
    return session_uuid


def get_user_from_session(session_uuid):
    global db
    q = {"session_uuid": session_uuid}
    session = db.session_to_user.find_one(q)

    if session:
        return session['email_address']
    return None


def store_access_token(access_token_dict):

    email_address = access_token_dict['email']

    global db

    # Close old crispin connection
    if email_address in email_address_to_crispins:
        crispin = email_address_to_crispins[email_address]
        crispin.stop()
        del email_address_to_crispins[email_address]

    access_token_dict["date"] = datetime.datetime.utcnow()
    access_token_dict['_id'] = ObjectId()

    session_id = db.user_email_to_token.insert(access_token_dict)


@tornado.gen.engine
def get_access_token(email_address, callback):
    global db
    q = {"email": email_address}
    cursor = db.user_email_to_token.find(q).sort([("date",-1)]).limit(1)
    try:
        access_token_dict = list(cursor)[0]
    except Exception, e:
        access_token_dict = None

    issued_date = access_token_dict['date']
    expires_seconds = access_token_dict['expires_in']

    buf = 60*5  # 5 minutes
    expire_date = issued_date + datetime.timedelta(seconds=expires_seconds+buf)

    expire_in = expire_date - datetime.datetime.utcnow()
    log.info("Oauth token expires in %s" % expire_in)

    # We need to refresh the token
    if (expire_date < datetime.datetime.utcnow() ):
        log.error("Need to update access token!")

        assert 'refresh_token' in access_token_dict
        refresh_token = access_token_dict['refresh_token']

        response = yield tornado.gen.Task(google_oauth.get_new_token, refresh_token)        

        # TODO Verify it and make sure it's valid. 
        assert 'access_token' in access_token_dict
        response['refresh_token'] = refresh_token

        store_access_token(response)
        access_token_dict = response

        log.info("Updated token for user %s" % access_token_dict['email'])

    callback(access_token_dict['access_token'])
    return 



def get_crispin_from_session(session, callback):
    """ Get the running crispin instance, or make a new one """
    email_address = get_user_from_session(session)
    return get_crispin_from_email(email_address)


@tornado.gen.engine
def get_crispin_from_email(email_address, callback):
    # TOFIX DEBUG
    if email_address is None: 
        email_address = 'mgrinich@gmail.com'

    if email_address in email_address_to_crispins:
        callback(email_address_to_crispins[email_address])
    else:
        access_token = yield tornado.gen.Task(get_access_token, email_address)        
        
        crispin_client =  crispin.CrispinClient(email_address, access_token)
        email_address_to_crispins[email_address] = crispin_client
        callback(crispin_client)


def stop_all_crispins():
    if not email_address_to_crispins: return
    for e,c in email_address_to_crispins.iteritems():
        c.stop()

