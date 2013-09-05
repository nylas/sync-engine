import logging as log

import json
import postel
from bson import json_util
from util import chunk
from models import db_session, MessageMeta, MessagePart, FolderMeta



class API(object):

    def messages_for_folder(self, user_id, folder_name):
        """ Load messages for folder. Returns JSON string which can be serialized to websocket """
        log.info('running messages_for_folder')

        all_g_msgids = db_session.query(FolderMeta.g_msgid).filter(FolderMeta.folder_name == folder_name).all()
        all_g_msgids = [s[0] for s in all_g_msgids]


        # TODO database calls should somehow be automatically wrapped in a greenlet

        all_msgs = []
        chunk_size = 100
        for g_msgids in chunk(all_g_msgids, chunk_size):
            all_msgs_query = db_session.query(MessageMeta).filter(MessageMeta.g_msgid.in_(g_msgids))
            result = all_msgs_query.all()
            all_msgs += result

        log.info('found %i messages' % len(all_msgs))

        return json.dumps([m.client_json() for m in all_msgs],
                           default=json_util.default)  # Fixes serializing date.datetime


    # TODO actually make this send mail with stuff etc.
    def send_mail(self, user_id, message_to_send):
        """ Sends a message with the given objects """

        # user = sessionmanager.verify_user(user)

        s = postel.SMTP(user.g_email,
                        user.g_access_token)

        s.setup()
        s.send_mail(message_to_send)
        s.quit()
        return "OK"


    def meta_with_id(self, user_id, data_id):

        existing_msgs_query = db_session.query(MessageMeta).filter(MessageMeta.g_msgid == data_id)
        log.info(existing_msgs_query)
        meta = existing_msgs_query.all()
        assert len(meta) == 1, "Incorrect messagemeta response"
        m = meta[0]

        existing_parts_query = db_session.query(MessagePart).filter(MessagePart.g_msgid == data_id)
        parts = existing_parts_query.all()

        print 'parts', parts


        return json.dumps([p.client_json() for p in parts],
                           default=json_util.default)

        # if to_fetch == plain_part:
        #     msg_data = encoding.plaintext2html(msg_data)  # Do this on the client
        # elif content_type == 'text/html':
            # msg_data = encoding.clean_html(msg_data)

    def start_sync(self, user_id):
        """ Talk to the Sync service and have it launch a sync. """
        pass

    def sync_status(self, user_id):
        """ Query Sync service for progress. """
        pass
