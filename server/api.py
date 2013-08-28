from crispin import AuthFailure, TooManyConnectionsFailure
import sessionmanager
import logging as log
import encoding

import json
import postel
from bson import json_util

from util import chunk


from sqlalchemy import *
from models import db_session, MessageMeta, MessagePart, FolderMeta


def messages_for_folder(folder_name, user):

    try:
        # TOFIX build streaming query api
        # def chunk_fetch(query, chunk_size):
        #     i = 0
        #     total_messages = query.count()
        #     all_items = []
        #     while i < total_messages - chunk_size:
        #         result = query.limit(chunk_size).offset( i ).all()
        #         all_items += [s[0] for s in result]
        #         i += chunk_size
        #     return all_items

        all_g_msgids = db_session.query(FolderMeta.g_msgid).filter(FolderMeta.folder_name == folder_name).all()
        all_g_msgids = [s[0] for s in all_g_msgids]

        all_msgs = []
        chunk_size = 100
        for g_msgids in chunk(all_g_msgids, chunk_size):
            all_msgs_query = db_session.query(MessageMeta).filter(MessageMeta.g_msgid.in_(g_msgids))
            result = all_msgs_query.all()
            all_msgs += result

        return json.dumps([m.client_json() for m in all_msgs],
                           default=json_util.default)  # Fixes serializing date.datetime



    except AuthFailure, e:
        log.error(e)
    except TooManyConnectionsFailure, e:
        log.error(e)
        return None


def send_mail(message_to_send, user=None):

    print message_to_send
    user = sessionmanager.verify_user(user)

    s = postel.SMTP(user.g_email,
                    user.g_access_token)

    s.setup()

    s.send_mail(message_to_send)
    s.quit()
    return "OK"




def data_with_id(data_id, user=None):
    assert user, "Must have user object."

    log.info('in data_with_id')

    existing_msgs_query = db_session.query(MessageMeta).filter(MessageMeta.g_msgid == data_id)
    log.info(existing_msgs_query)
    meta = existing_msgs_query.all()
    assert len(meta) == 1, "We haven't synced metadata for this message..."
    m = meta[0]


    existing_parts_query = db_session.query(MessagePart).filter(MessagePart.g_msgid == data_id)
    parts = existing_parts_query.all()
    print 'parts', len(parts)

    return json.dumps([p.client_json() for p in parts],
                       default=json_util.default)

    # if to_fetch == plain_part:
    #     msg_data = encoding.plaintext2html(msg_data)  # Do this on the client
    # elif content_type == 'text/html':
        # msg_data = encoding.clean_html(msg_data)
