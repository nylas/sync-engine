import logging as log

import json
import postel
from bson import json_util
from models import db_session, MessageMeta, FolderMeta, SharedFolderNSMeta, BlockMeta, Namespace, User, IMAPAccount

from sqlalchemy.orm import joinedload

import zerorpc
import os

class API(object):

    _zmq_search = None
    @property
    def z_search(self):
        """ Proxy function for the ZeroMQ search service. """
        if not self._zmq_search:
            self._zmq_search = zerorpc.Client(
                    os.environ.get('SEARCH_SERVER_LOC', None))
        return self._zmq_search.search

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
        return json.dumps(status, default=json_util.default)

    def search_folder(self, namespace_id, search_query):
        results = self.z_search(namespace_id, search_query)
        meta_ids = [r[0] for r in results]
        return json.dumps(meta_ids, default=json_util.default)

    def messages_for_folder(self, namespace_id, folder_name):
        """ Returns all messages in a given folder.

            Note that this may be more messages than included in the IMAP
            folder, since we fetch the full thread if one of the messages is in
            the requested folder.
        """
        # save a database call by just creating a new namespace object and
        # not committing it to the db
        messages = Namespace(id=namespace_id).get_messages(folder_name)

        log.info('found {0} message IDs'.format(len(messages)))
        return json.dumps([m.client_json() for m in messages],
                           default=json_util.default)  # Fixes serializing date.datetime

    def messages_with_ids(self, namespace_id, msg_ids):
        """ Returns MessageMeta objects for the given msg_ids """
        all_msgs_query = db_session.query(MessageMeta)\
            .filter(MessageMeta.id.in_(msg_ids), 
                    MessageMeta.namespace_id == namespace_id)
        all_msgs = all_msgs_query.all()

        log.info('found %i messages IDs' % len(all_msgs))
        return json.dumps([m.client_json() for m in all_msgs],
                           default=json_util.default)  # Fixes serializing date.datetime


    def send_mail(self, namespace_id, recipients, subject, body):
        """ Sends a message with the given objects """

        account = db_session.query(IMAPAccount).join(Namespace).filter(
                Namespace.id==namespace_id).one()
        with postel.SMTP(account) as smtp:
            smtp.send_mail(recipients, subject, body)
        return "OK"

    def meta_with_id(self, namespace_id, data_id):
        existing_msgs_query = db_session.query(MessageMeta).join(Namespace)\
                .filter(MessageMeta.g_msgid == data_id, Namespace.id == namespace_id)\
                .options(joinedload("parts"))
        meta = existing_msgs_query.all()
        if not len(meta) == 1:
            log.error("messagemeta query returned %i results" % len(meta))
        if len(meta) == 0: return []
        m = meta[0]

        parts = m.parts

        return json.dumps([p.client_json() for p in parts],
                           default=json_util.default)

    def part_with_id(self, namespace_id, message_id, walk_index):
        q = db_session.query(BlockMeta).join(MessageMeta)\
                .filter(MessageMeta.g_msgid==message_id,
                        BlockMeta.walk_index == walk_index,
                        MessageMeta.namespace_id == namespace_id)
        parts = q.all()
        print 'parts', len(parts)
        if not len(parts) > 0:
            log.error("No part to return... should have some data!")
            data = {'message_data' : '' }
        else:
            if len(parts) > 1:
                log.info("This part is in multiple folders")
            part = parts[0]
            data = {'message_data': part.get_data() }

        # if to_fetch == plain_part:
        #     msg_data = encoding.plaintext2html(msg_data)  # Do this on the client
        # elif content_type == 'text/html':
            # msg_data = encoding.clean_html(msg_data)

        return json.dumps(data,
                           default=json_util.default)  # Fixes serializing date.datetime

        # existing_message_part = db_session.query(MessageMeta).filter(MessageMeta.g_msgid == data_id).filter(MessageMeta.g_namespace_id == user_id)

    def top_level_namespaces(self, user_id):
        """for the user, get the namespaces for all the accounts associated as well as all the shared folder metas
        returns a list of tuples of display name, type, and id"""
        nses = {'private': {}, 'shared': {}}

        accounts = db_session.query(IMAPAccount).filter(IMAPAccount.user_id == user_id)
        for account in accounts:
            account_ns = account.namespace
            nses['private'][account_ns.id] = 'Gmail'

        shared_nses = db_session.query(SharedFolderNSMeta)\
                .filter(SharedFolderNSMeta.user_id == user_id)
        for shared_ns in shared_nses:
            nses['shared'][shared_ns.id] = shared_ns.display_name

        print nses
        return json.dumps(nses, default=json_util.default)

    def start_sync(self, namespace_id):
        """ Talk to the Sync service and have it launch a sync. """
        pass

