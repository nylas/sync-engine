import logging as log

import json
import postel
from bson import json_util
from util import chunk
from models import db_session, MessageMeta, MessagePart, FolderMeta, User

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

    def search_folder(self, user_id, search_query):
        results = self.z_search(user_id, search_query)

        meta_ids = [r[0] for r in results]

        return json.dumps(meta_ids, default=json_util.default)

    def messages_for_folder(self, user_id, folder_name):
        """ Returns all messages in a given folder.
            Noe that this may be more messages than included in the IMAP folder, since
            we fetch the full thread if one of the messages is in the requested folder.
        """

        all_g_msgids = db_session.query(FolderMeta.g_msgid).filter(FolderMeta.folder_name == folder_name).all()
        all_g_msgids = [s[0] for s in all_g_msgids]


        # Get all thread IDs
        all_thrids = set()
        for g_msgids in chunk(all_g_msgids, db_chunk_size):
            all_msgs_query = db_session.query(MessageMeta.g_thrid).filter(MessageMeta.g_msgid.in_(g_msgids))
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



    def messages_with_ids(self, user_id, msg_ids):
        """ Returns MessageMeta objects for the given msg_ids """
        all_msgs_query = db_session.query(MessageMeta).filter(MessageMeta.id.in_(msg_ids))
        all_msgs = all_msgs_query.all()

        log.info('found %i messages IDs' % len(all_msgs))
        return json.dumps([m.client_json() for m in all_msgs],
                           default=json_util.default)  # Fixes serializing date.datetime




    # TODO actually make this send mail with stuff etc.
    def send_mail(self, user_id, message_to_send):
        """ Sends a message with the given objects """

        # TODO have postel take user_id instead of email/token
        user = db_session.query(User).filter(User.id == user_id).all()[0]
        s = postel.SMTP(user.g_email,
                        user.g_access_token)

        s.setup()
        s.send_mail(message_to_send)
        s.quit()
        return "OK"


    def meta_with_id(self, user_id, data_id):

        existing_msgs_query = db_session.query(MessageMeta).join(User)\
                .filter(MessageMeta.g_msgid == data_id, User.id == user_id)\
                .options(joinedload("parts"))
        log.info(existing_msgs_query)
        meta = existing_msgs_query.all()
        assert len(meta) == 1, "Incorrect messagemeta response"
        m = meta[0]

        parts = m.parts

        return json.dumps([p.client_json() for p in parts],
                           default=json_util.default)

    def part_with_id(self, user_id, message_id, walk_index):

        print 'user_id:', user_id
        print 'message_id', message_id
        print 'walk_index', walk_index

        # TODO store MessageParts rows by user_id instead of email address
        # user = db_session.query(User).filter(User.user_id == user_id).all()[0]


        q = db_session.query(MessagePart).join(MessageMeta)\
                .filter(MessageMeta.g_msgid==message_id,
                        MessagePart.walk_index == walk_index)
        parts = q.all()
        print 'parts', parts

        assert len(parts) == 1
        part = parts[0]


        print 'type:', type(part.get_data())

        data = {'message_data': part.get_data() }

        # if to_fetch == plain_part:
        #     msg_data = encoding.plaintext2html(msg_data)  # Do this on the client
        # elif content_type == 'text/html':
            # msg_data = encoding.clean_html(msg_data)



        return json.dumps(data,
                           default=json_util.default)  # Fixes serializing date.datetime

        # existing_message_part = db_session.query(MessageMeta).filter(MessageMeta.g_msgid == data_id).filter(MessageMeta.g_user_id == user_id)



    def start_sync(self, user_id):
        """ Talk to the Sync service and have it launch a sync. """
        pass

    def sync_status(self, user_id):
        """ Query Sync service for progress. """
        pass
