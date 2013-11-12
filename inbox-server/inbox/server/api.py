import os
import json

from functools import wraps
from sqlalchemy import distinct

import zerorpc

import postel
from bson import json_util
from models import db_session, Message, FolderItem, SharedFolder, Thread
from models import Namespace, User, IMAPAccount, TodoNamespace, TodoItem

from ..util.itert import chunk

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
    def messages_for_folder(self, folder_name):
        """ Returns all messages in a given folder.

            Note that this may be more messages than included in the IMAP
            folder, since we fetch the full thread if one of the messages is in
            the requested folder.
        """
        imapaccount_id = self.namespace.imapaccount_id
        all_thrids = set([thrid for thrid, in db_session.query(
            distinct(Message.thread_id)).join(FolderItem) \
              .filter(FolderItem.folder_name == folder_name,
                      FolderItem.imapaccount_id == imapaccount_id).all()])

        log.error("thrids: {0}".format(all_thrids))

        # Get all messages for those thread IDs
        messages = []
        DB_CHUNK_SIZE = 100
        for thrids in chunk(list(all_thrids), DB_CHUNK_SIZE):
            all_msgs_query = db_session.query(Thread).join(Thread.messages) \
                    .filter(Thread.id.in_(thrids),
                            Message.namespace_id == self.namespace_id)
            for thread in all_msgs_query:
                messages.extend(thread.messages)

        log.info('found {0} message IDs'.format(len(messages)))
        return [m.cereal() for m in messages]

    @jsonify
    def messages_with_ids(self, namespace_id, msg_ids):
        """ Returns Message objects for the given msg_ids """
        all_msgs_query = db_session.query(Message)\
            .filter(Message.id.in_(msg_ids),
                    Message.namespace_id == namespace_id)
        all_msgs = all_msgs_query.all()

        log.info('found %i messages IDs' % len(all_msgs))
        return [m.cereal() for m in all_msgs]

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
        """for the user, get the namespaces for all the accounts associated as well as all the shared folder metas
        returns a list of tuples of display name, type, and id"""
        nses = {'private': [], 'shared': []}

        user = db_session.query(User).join(IMAPAccount).get(user_id)
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
    def create_todo(self, g_thrid):
        log.info('creating todo from namespace {0} g_thrid {1}'.format(self.namespace_id, g_thrid))

        # TODO abstract this logic out
        messages_in_thread = db_session.query(Message).filter(
                Message.namespace_id == self.namespace_id,
                Message.g_thrid == g_thrid).all()

        todo_ns = get_or_create_todo_namespace(self.user_id)
        for message in messages_in_thread:
            message.namespace_id = todo_ns.id

        todo_item = TodoItem(
                g_thrid = g_thrid,
                imapaccount_id = self.namespace.imapaccount_id,
                namespace_id = todo_ns.id,
                display_name = messages_in_thread[0].subject,
                due_date = 'Soon',
                date_completed = None,
                sort_index = 0,
            )
        db_session.add(todo_item)
        db_session.commit()
        return "OK"

    def start_sync(self, namespace_id):
        """ Talk to the Sync service and have it launch a sync. """
        pass
