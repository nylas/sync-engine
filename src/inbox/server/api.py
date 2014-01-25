import os
import json

from functools import wraps
from bson import json_util

import zerorpc

from . import postel
from .config import config
from .models import session_scope
from .models.tables import Message, SharedFolder, User, ImapAccount
from .models.namespace import threads_for_folder

from .log import get_logger
log = get_logger()

class NSAuthError(Exception):
    pass

def namespace_auth(fn):
    """
    decorator that checks whether user has permissions to access namespace
    """
    @wraps(fn)
    def namespace_auth_fn(self, user_id, namespace_id, *args, **kwargs):

        print "user_id, namespace_id, config = ", user_id, namespace_id, config

        with session_scope() as db_session:
            self.user_id = user_id
            self.namespace_id = namespace_id
            user = db_session.query(User).filter_by(id=user_id).join(ImapAccount).one()
            for account in user.imapaccounts:
                if account.namespace.id == namespace_id:
                    self.namespace = account.namespace
                    return fn(self, *args, **kwargs)

            shared_nses = db_session.query(SharedFolder)\
                    .filter(SharedFolder.user_id == user_id)
            for shared_ns in shared_nses:
                if shared_ns.id == namespace_id:
                    return fn(self, *args, **kwargs)

            raise NSAuthError("User '{0}' does not have access to namespace '{1}'".format(user_id, namespace_id))

    return namespace_auth_fn

def jsonify(fn):
    """ decorator that JSONifies a function's return value """
    def wrapper(*args, **kwargs):
        ret = fn(*args, **kwargs)
        return json.dumps(ret, default=json_util.default) # fixes serializing date.datetime
    return wrapper

class API(object):

    _zmq_search = None
    @property
    def z_search(self):
        """ Proxy function for the ZeroMQ search service. """
        if not self._zmq_search:
            search_srv_loc = config.get('SEARCH_SERVER_LOC', None)
            assert search_srv_loc, "Where is the Search ZMQ service?"
            self._zmq_search = zerorpc.Client(search_srv_loc)
        return self._zmq_search.search

    @jsonify
    def sync_status(self):
        """ Returns data representing the status of all syncing users, like:

            user_id: {
                state: 'initial sync',
                stored_data: '12127227',
                stored_messages: '50000',
                status: '56%',
            }
            user_id: {
                state: 'poll',
                stored_data: '1000000000',
                stored_messages: '200000',
                status: '2013-06-08 14:00',
            }
        """
        if not self._sync:
            self._sync = zerorpc.Client(os.environ.get('CRISPIN_SERVER_LOC', None))
        status = self._sync.status()
        user_ids = status.keys()
        with session_scope() as db_session:
            users = db_session.query(User).filter(User.id.in_(user_ids))
            for user in users:
                status[user.id]['stored_data'] = user.total_stored_data()
                status[user.id]['stored_messages'] = user.total_stored_messages()
            return status

    @namespace_auth
    @jsonify
    def search_folder(self, search_query):
        log.info("Searching with query: {0}".format(search_query))
        results = self.z_search(self.namespace.id, search_query)
        message_ids = [r[0] for r in results]
        log.info("Found {0} messsages".format(len(message_ids)))
        return message_ids

    @namespace_auth
    @jsonify
    def threads_for_folder(self, folder_name):
        """ Returns all threads in a given folder, together with associated
            messages. Supports shared folders and TODO namespaces as well, if
            caller auths with that namespace.

            Note that this may be more messages than included in the IMAP
            folder, since we fetch the full thread if one of the messages is in
            the requested folder.
        """
        with session_scope() as db_session:
            return [t.cereal() for t in threads_for_folder(self.namespace.id,
                        db_session, folder_name)]

    @namespace_auth
    def send_mail(self, recipients, subject, body):
        """ Sends a message with the given objects """
        account = self.namespace.imapaccount
        assert account is not None, "can't send mail with this namespace"
        if type(recipients) != list:
            recipients = [recipients]
        with postel.SMTP(account) as smtp:
            smtp.send_mail(recipients, subject, body)
        return "OK"

    @namespace_auth
    @jsonify
    def body_for_message(self, message_id):
        with session_scope() as db_session:
            message = db_session.query(Message).join(Message.parts) \
                    .filter(Message.id==message_id,
                            Message.namespace_id==self.namespace.id).one()

            return {'data': message.prettified_body}

    @jsonify
    def top_level_namespaces(self, user_id):
        """ For the user, get the namespaces for all the accounts associated as
            well as all the shared folder rows.

            returns a list of tuples of display name, type, and id
        """
        nses = {'private': [], 'shared': [] }

        with session_scope() as db_session:
            user = db_session.query(User).join(ImapAccount)\
                    .filter_by(id=user_id).one()

            for account in user.imapaccounts:
                account_ns = account.namespace
                nses['private'].append(account_ns.cereal())

            shared_nses = db_session.query(SharedFolder)\
                    .filter(SharedFolder.user_id == user_id)
            for shared_ns in shared_nses:
                nses['shared'].append(shared_ns.cereal())

            return nses

    # Mailing list API:
    @namespace_auth
    def is_mailing_list_message(self, message_id):
        with session_scope() as db_session:
            message = db_session.query(Message).filter(Message.id==message_id).one()

            return (message.mailing_list_info != None)

    @namespace_auth
    @jsonify
    def mailing_list_info_for_message(self, message_id):
        with session_scope() as db_session:
            message = db_session.query(Message).filter(Message.id==message_id).one()

            return message.mailing_list_info

    # Headers API:
    @namespace_auth
    @jsonify
    def headers_for_message(self, message_id):
        with session_scope() as db_session:
            message = db_session.query(Message).filter(Message.id==message_id).one()

            return message.headers
