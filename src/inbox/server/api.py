import json
import uuid

from functools import wraps
from bson import json_util

import zerorpc

from inbox.server.actions import base as actions
from inbox.server.config import config
from inbox.server.contacts import search_util
from inbox.server.models import session_scope
from inbox.server.mailsync.backends.imap.account import (total_stored_data,
                                                         total_stored_messages)
from inbox.server.models.tables.base import (Message, SharedFolder, User,
                                             Account, Contact, Thread)
from inbox.server.models.namespace import (threads_for_folder,
                                           archive_thread, move_thread,
                                           copy_thread, delete_thread)
from inbox.server.sendmail.base import send
from inbox.server.log import get_logger
log = get_logger(purpose='api')

# Provider name for contacts added via this API
INBOX_PROVIDER_NAME = 'inbox'


class NSAuthError(Exception):
    pass


def namespace_auth(fn):
    """
    decorator that checks whether user has permissions to access namespace
    """
    @wraps(fn)
    def namespace_auth_fn(self, user_id, namespace_id, *args, **kwargs):
        with session_scope() as db_session:
            self.user_id = user_id
            self.namespace_id = namespace_id
            user = db_session.query(User).filter_by(id=user_id).join(
                Account).one()
            for account in user.accounts:
                if account.namespace.id == namespace_id:
                    self.namespace = account.namespace
                    return fn(self, *args, **kwargs)

            shared_nses = db_session.query(SharedFolder)\
                .filter(SharedFolder.user_id == user_id)
            for shared_ns in shared_nses:
                if shared_ns.id == namespace_id:
                    return fn(self, *args, **kwargs)

            raise NSAuthError("User '{0}' does not have access to namespace\
                '{1}'".format(user_id, namespace_id))

    return namespace_auth_fn


def jsonify(fn):
    """ decorator that JSONifies a function's return value """
    def wrapper(*args, **kwargs):
        ret = fn(*args, **kwargs)
        # fixes serializing date.datetime
        return json.dumps(ret, default=json_util.default)
    return wrapper


class API(object):
    _zmq_search = None
    _sync = None

    # Remember, ZeroRPC doesn't support keyword arguments in exposed methods

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
            self._sync = zerorpc.Client(config.get('CRISPIN_SERVER_LOC', None))
        status = self._sync.status()
        user_ids = status.keys()
        with session_scope() as db_session:
            users = db_session.query(User).filter(User.id.in_(user_ids))
            for user in users:
                status[user.id]['stored_data'] = 0
                status[user.id]['stored_messages'] = 0
                for account in user.accounts:
                    status[user.id]['stored_data'] += \
                        total_stored_data(account.id, db_session)
                    status[user.id]['stored_messages'] += \
                        total_stored_messages(account.id, db_session)
            return status

    @namespace_auth
    def send_mail(self, recipients, subject, body, attachments=None):
        """ Sends a message with the given objects """
        account = self.namespace.account
        assert account is not None, "Can't send mail with this namespace"

        if type(recipients) != list:
            recipients = [recipients]

        send(account, recipients, subject, body, attachments)

        return 'OK'

    # TODO[k]: Update this
    @namespace_auth
    def reply_to_thread(self, thread_id, body, attachments=None):
        account = self.namespace.account
        assert account is not None, "Can't send mail with this namespace"

        raise NotImplementedError

    @jsonify
    def top_level_namespaces(self, user_id):
        """ For the user, get the namespaces for all the accounts associated as
            well as all the shared folder rows.

            returns a list of tuples of display name, type, and id
        """
        nses = {'private': [], 'shared': []}

        with session_scope() as db_session:
            user = db_session.query(User).join(Account)\
                .filter_by(id=user_id).one()

            for account in user.accounts:
                account_ns = account.namespace
                nses['private'].append(account_ns.cereal())

            shared_nses = db_session.query(SharedFolder)\
                .filter(SharedFolder.user_id == user_id)
            for shared_ns in shared_nses:
                nses['shared'].append(shared_ns.cereal())

            return nses

    @namespace_auth
    @jsonify
    def search_folder(self, search_query):
        log.info("Searching with query: {0}".format(search_query))
        results = self.z_search(self.namespace.id, search_query)
        message_ids = [r[0] for r in results]
        log.info("Found {0} messages".format(len(message_ids)))
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
            return [t.cereal() for t in threads_for_folder(
                self.namespace.id, db_session, folder_name)]

    @namespace_auth
    @jsonify
    def body_for_message(self, message_id):
        # TODO: Take namespace into account, currently doesn't matter since
        # one namespace only.
        with session_scope() as db_session:
            message = db_session.query(Message).join(Message.parts) \
                .filter(Message.id == message_id).one()
            return {'data': message.prettified_body}

    # Headers API:
    @namespace_auth
    @jsonify
    def headers_for_message(self, message_id):
        # TODO[kavya]: Take namespace into account, currently doesn't matter
        # since one namespace only.
        with session_scope() as db_session:
            message = db_session.query(Message).filter(
                Message.id == message_id).one()
            return message.headers

    # Mailing list API:
    @namespace_auth
    def is_mailing_list_thread(self, thread_id):
        with session_scope() as db_session:
            thread = db_session.query(Thread).filter(
                Thread.id == thread_id,
                Thread.namespace_id == self.namespace.id).one()
            return thread.is_mailing_list_thread()

    @namespace_auth
    @jsonify
    def mailing_list_info_for_thread(self, thread_id):
        with session_scope() as db_session:
            thread = db_session.query(Thread).filter(
                Thread.id == thread_id,
                Thread.namespace_id == self.namespace.id).one()
            return thread.mailing_list_info

    # For first_10_subjects example:
    def first_n_subjects(self, n):
        with session_scope() as db_session:
            subjects = db_session.query(Thread.subject).limit(n).all()
            return subjects

    ### actions that need to be synced back to the account backend
    ### (we use a task queue to ensure reliable syncing)

    @namespace_auth
    @jsonify
    def archive(self, thread_id):
        """ Archive thread locally and also sync back to the backend. """
        account = self.namespace.account
        assert account is not None, "can't archive mail with this namespace"

        # make local change
        with session_scope() as db_session:
            archive_thread(self.namespace.id, db_session, thread_id)

        # sync it to the account backend
        q = actions.get_queue()
        q.enqueue(actions.get_archive_fn(account), account.id, thread_id)

        # XXX TODO register a failure handler that reverses the local state
        # change if the change fails to go through---this could cause our
        # repository to get out of sync with the remote if another client
        # does the same change in the meantime and we apply that change and
        # *then* the change reversal goes through... but we can make this
        # eventually consistent by doing a full comparison once a day or
        # something.

        return "OK"

    @namespace_auth
    @jsonify
    def move(self, thread_id, from_folder, to_folder):
        """ Move thread locally and also sync back to the backend. """
        account = self.namespace.account
        assert account is not None, "can't move mail with this namespace"

        # make local change
        with session_scope() as db_session:
            move_thread(self.namespace.id, db_session, thread_id, from_folder,
                        to_folder)

        # sync it to the account backend
        q = actions.get_queue()
        q.enqueue(actions.get_move_fn(account), account.id, thread_id,
                  from_folder, to_folder)

        # XXX TODO register a failure handler that reverses the local state
        # change if the change fails to go through

        return "OK"

    @namespace_auth
    @jsonify
    def copy(self, thread_id, from_folder, to_folder):
        """ Copy thread locally and also sync back to the backend. """
        account = self.namespace.account
        assert account is not None, "can't copy mail with this namespace"

        # make local change
        with session_scope() as db_session:
            copy_thread(self.namespace.id, db_session, thread_id,
                        from_folder, to_folder)

        # sync it to the account backend
        q = actions.get_queue()
        q.enqueue(actions.get_copy_fn(account), account.id, thread_id,
                  from_folder, to_folder)

        # XXX TODO register a failure handler that reverses the local state
        # change if the change fails to go through

        return "OK"

    @namespace_auth
    @jsonify
    def delete(self, thread_id, folder_name):
        """ Delete thread locally and also sync back to the backend.

        This really just removes the entry from the folder. Message data that
        no longer belongs to any messages is garbage-collected asynchronously.
        """
        account = self.namespace.account
        assert account is not None, "can't delete mail with this namespace"

        # make local change
        with session_scope() as db_session:
            delete_thread(self.namespace.id, db_session, thread_id,
                          folder_name)

        # sync it to the account backend
        q = actions.get_queue()
        q.enqueue(actions.get_delete_fn(account), account.id, thread_id,
                  folder_name)

        # XXX TODO register a failure handler that reverses the local state
        # change if the change fails to go through

        return "OK"

    def get_contact(self, contact_id):
        """Get all data for an existing contact."""
        with session_scope() as db_session:
            contact = db_session.query(Contact).filter_by(id=contact_id).one()
            return contact.cereal()

    def add_contact(self, account_id, contact_info):
        """Add a new contact to the specified IMAP account. Returns the ID of
        the added contact."""
        with session_scope() as db_session:
            contact = Contact(account_id=account_id, source='local',
                              provider_name=INBOX_PROVIDER_NAME,
                              uid=uuid.uuid4())
            contact.from_cereal(contact_info)
            db_session.add(contact)
            db_session.commit()
            log.info("Added contact {0}".format(contact.id))
            return contact.id

    def update_contact(self, contact_id, contact_data):
        """Update data for an existing contact."""
        with session_scope() as db_session:
            contact = db_session.query(Contact).filter_by(id=contact_id).one()
            contact.from_cereal(contact_data)
            log.info("Updated contact {0}".format(contact.id))
            return 'OK'

    def search_contacts(self, account_id, query, max_results=10):
        """Search for contacts that match the given query."""
        with session_scope() as db_session:
            results = search_util.search(db_session, account_id, query,
                                         int(max_results))
            return [contact.cereal() for contact in results]
