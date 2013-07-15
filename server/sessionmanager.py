import crispin
import uuid

import pymongo
# from bson.objectid import ObjectId
import logging as log
import datetime

class SessionManager():

    db = None

    # Memory cache for currently open crispin instances
    email_address_to_crispins = {}

    @classmethod
    def setup(cls):
        
        cls.db = pymongo.MongoClient().test

        try:
            cls.db.create_collection('session_to_user')
            cls.db.create_collection('user_email_to_token')
            log.info('Created collections in sessions DB"')
        except pymongo.errors.CollectionInvalid, e:
            if cls.db.create_collection and cls.db.create_collection:
                log.info("DB exists already.")
            else:
                log.error("Error creating sessions DB collecitons. %s" % e)


    @classmethod
    def store_session(cls, email_address):
        session_uuid = str(uuid.uuid1())

        session = {"email_address": email_address,
                   "session_uuid": session_uuid,
                   "date": datetime.datetime.utcnow()
                   }
        session_id = cls.db.session_to_user.insert(session)
        return session_uuid


    @classmethod
    def get_user(cls, session_uuid):

        q = {"session_uuid": session_uuid}
        session = cls.db.session_to_user.find_one(q)

        if session:
            return session['email_address']
        return None



    @classmethod
    def store_access_token(cls, email_address, access_token):

        # Not valid anymore
        if email_address in cls.email_address_to_crispins:
            crispin = cls.email_address_to_crispins[email_address]
            crispin.stop()
            del cls.email_address_to_crispins[email_address]


        token_doc = {"email_address": email_address,
                    "access_token": access_token,
                    "date": datetime.datetime.utcnow()
                   }
        session_id = cls.db.user_email_to_token.insert(token_doc)


    @classmethod
    def get_access_token(cls, email_address):
        q = {"email_address": email_address}
        cursor = cls.db.user_email_to_token.find(q).sort([("date",-1)]).limit(1)
        try:
            entries = list(cursor)[0]
            return entries['access_token']
        except Exception, e:
            return None


    @classmethod
    def get_crispin(cls, session=None):

        # convert session to usr
        # convert usr to crisin

        if session is None:
            email_address = 'mgrinich@gmail.com'
        else:
            email_address = self.get_user(session)


        if email_address in cls.email_address_to_crispins:
            return cls.email_address_to_crispins[email_address]
        else:
            access_token = SessionManager.get_access_token(email_address)
            crispin_client =  crispin.CrispinClient(email_address, access_token)
            cls.email_address_to_crispins[email_address] = crispin_client
            return crispin_client



    @classmethod
    def stop_all_crispins(cls):

        for c in cls.email_address_to_crispins.values():
            c.stop()
        cls.email_address_to_crispins = {}
