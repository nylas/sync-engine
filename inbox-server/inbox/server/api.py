import os
import json

from functools import wraps

import zerorpc

import postel
from bson import json_util
from models import db_session, Message, SharedFolder, Thread
from models import Namespace, User, IMAPAccount, TodoNamespace, TodoItem

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
        self.user_id = user_id
        self.namespace_id = namespace_id
        user = db_session.query(User).filter_by(id=user_id).join(IMAPAccount).one()
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

# should this be moved to model.py or similar?
def get_or_create_todo_namespace(user_id):
    user = db_session.query(User).join(TodoNamespace, Namespace, TodoItem) \
            .get(user_id)
    if user.todo_namespace is not None:
        return user.todo_namespace.namespace

    # create a todo namespace
    todo_ns = Namespace(imapaccount_id=None, namespace_type='todo')
    db_session.add(todo_ns)
    db_session.commit()

    todo_namespace = TodoNamespace(namespace_id=todo_ns.id, user_id=user_id)
    db_session.add(todo_namespace)
    db_session.commit()

    log.info('todo namespace id {0}'.format(todo_ns.id))
    return todo_ns

class API(object):

    _zmq_search = None
    @property
    def z_search(self):
        """ Proxy function for the ZeroMQ search service. """
        if not self._zmq_search:
            self._zmq_search = zerorpc.Client(
                    os.environ.get('SEARCH_SERVER_LOC', None))
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
        users = db_session.query(User).filter(User.id.in_(user_ids))
        for user in users:
            status[user.id]['stored_data'] = user.total_stored_data()
            status[user.id]['stored_messages'] = user.total_stored_messages()
        return status

    @jsonify
    def search_folder(self, namespace_id, search_query):
        results = self.z_search(namespace_id, search_query)
        meta_ids = [r[0] for r in results]
        return meta_ids

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
        return [t.cereal() for t in \
                self.namespace.threads_for_folder(folder_name)]

    def send_mail(self, namespace_id, recipients, subject, body):
        """ Sends a message with the given objects """

        account = db_session.query(IMAPAccount).join(Namespace).filter(
                Namespace.id==namespace_id).one()
        with postel.SMTP(account) as smtp:
            smtp.send_mail(recipients, subject, body)
        return "OK"

    @namespace_auth
    @jsonify
    def body_for_message(self, message_id):
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
        nses = {'private': [], 'shared': [], 'todo': []}

        user = db_session.query(User).join(IMAPAccount) \
                .join(TodoNamespace).get(user_id)

        nses['todo'].append(user.todo_namespace.cereal())

        for account in user.imapaccounts:
            account_ns = account.namespace
            nses['private'].append(account_ns.cereal())

        shared_nses = db_session.query(SharedFolder)\
                .filter(SharedFolder.user_id == user_id)
        for shared_ns in shared_nses:
            nses['shared'].append(shared_ns.cereal())

        return nses

    @jsonify
    def todo_items(self, user_id):
        todo_ns = get_or_create_todo_namespace(user_id)
        todo_items = todo_ns.todo_items
        return [i.cereal() for i in todo_items]

    @namespace_auth
    def create_todo(self, thread_id):
        log.info('creating todo from namespace {0} thread_id {1}'.format(
            self.namespace_id, thread_id))

        thread = db_session.query(Thread).join(Thread.messages)\
                .filter_by(id=thread_id).one()

        todo_ns = get_or_create_todo_namespace(self.user_id)
        log.info('todo namespace is: {0}'.format(todo_ns.id))
        for message in thread.messages:
            message.namespace_id = todo_ns.id

        thread.namespace_id = todo_ns.id

        todo_item = TodoItem(
                thread_id = thread_id,
                imapaccount_id = self.namespace.imapaccount_id,
                namespace_id = todo_ns.id,
                display_name = thread.messages[0].subject,
                due_date = 'Soon',
                date_completed = None,
                sort_index = 0,
            )
        db_session.add(todo_item)
        db_session.add(thread)
        db_session.commit()
        return "OK"
