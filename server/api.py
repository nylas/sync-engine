import logging as log

import json
import postel
from bson import json_util
from util.itert import chunk
from models import db_session, MessageMeta, BlockMeta, FolderMeta, Namespace, User

from sqlalchemy.orm import joinedload

db_chunk_size = 100

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

        all_msgids = db_session.query(FolderMeta.messagemeta_id)\
              .filter(FolderMeta.folder_name == folder_name,
                      FolderMeta.namespace_id == namespace_id).all()
        all_msgids = [s[0] for s in all_msgids]


        # Get all thread IDs
        all_thrids = set()
        for msgids in chunk(all_msgids, db_chunk_size):
            all_msgs_query = db_session.query(MessageMeta.g_thrid).filter(MessageMeta.id.in_(msgids))
            result = all_msgs_query.all()
            [all_thrids.add(s[0]) for s in result]


        # Get all messages for those thread IDs
        all_msgs = []
        for g_thrids in chunk(list(all_thrids), db_chunk_size):
            all_msgs_query = db_session.query(MessageMeta).filter(MessageMeta.g_thrid.in_(g_thrids))
            result = all_msgs_query.all()
            all_msgs += result

        log.info('found %i messages IDs' % len(all_msgs))
        return json.dumps([m.client_json() for m in all_msgs],
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




    # TODO actually make this send mail with stuff etc.
    def send_mail(self, namespace_id, message_to_send):
        """ Sends a message with the given objects """

        # TODO have postel take namespace_id instead of email/token
        user = db_session.query(Namespace).filter(
                Namespace.id == namespace_id).all()[0]
        s = postel.SMTP(user.g_email,
                        user.g_access_token)

        s.setup()
        s.send_mail(message_to_send)
        s.quit()
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

        # TODO store BlockMetas rows by namespace_id instead of email address
        # user = db_session.query(User).filter(User.namespace_id == user_id).all()[0]

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



    def start_sync(self, namespace_id):
        """ Talk to the Sync service and have it launch a sync. """
        pass

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
