import crispin
import uuid


class SessionManager():

    session_to_user = {}
    user_email_to_token = {}
    email_address_to_crispins = {}


    @classmethod
    def store_session(cls, email_address):
        session_uuid = str(uuid.uuid1())
        cls.session_to_user[session_uuid] = email_address
        return session_uuid


    @classmethod
    def store_access_token(cls, email_address, access_token):

        # Not valid anymore
        if email_address in cls.email_address_to_crispins:
            cls.mail_address_to_crispins[email_address].stop()

        if email_address in cls.user_email_to_token:
            log.info("Updating oauth token for user %s" % email_address)
        cls.user_email_to_token[email_address] = access_token


    @classmethod
    def get_access_token(cls, email_address):
        if email_address in cls.user_email_to_token:
            return cls.user_email_to_token[email_address]
        return None



    @classmethod
    def get_user(cls, session):
        try:
            return cls.session_to_user[session]
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
            access_token = cls.user_email_to_token[email_address]
            return crispin.CrispinClient(email_address, access_token)


    @classmethod
    def stop_all_crispins(cls):

        for c in cls.email_address_to_crispins.values():
            c.stop()
