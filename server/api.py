from crispin import AuthFailure, TooManyConnectionsFailure
import sessionmanager
import logging as log
import encoding

import json
import postel
from bson import json_util

from util import chunk


from sqlalchemy import *
from models import db_session, Base, MessageMeta, MessagePart, FolderMeta


def messages_for_folder(folder_name="\Inbox", user=None):
    assert user, "Must have user for operation"

    folder_name = "MITERS"

    try:
        # crispin_client = sessionmanager.get_crispin_from_email(email_address)
        # log.info('fetching threads...')
        # threads = crispin_client.fetch_messages(folder_name)

        def chunk_fetch(query, chunk_size):
            i = 0
            total_messages = query.count()
            all_items = []
            while i < total_messages - chunk_size:
                result = query.limit(chunk_size).offset( i ).all()
                all_items += [s[0] for s in result]
                i += chunk_size
            return all_items


        rows = db_session.query(FolderMeta.g_msgid).filter(FolderMeta.folder_name == folder_name)
        all_g_msgids = chunk_fetch(rows, 200)


        all_msgs = []
        chunk_size = 200
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
    print 'parts', parts

    plain_part = None
    html_part = None
    for part in parts:
        if part.content_type == 'text/html':
            html_part = part
        if part.content_type == 'text/plain':
            plain_part = part

    to_fetch = html_part if html_part else plain_part

    crispin_client = sessionmanager.get_crispin_from_email(user.g_email)

    msg_data = crispin_client.fetch_msg_body(m.uid, to_fetch.section)
    msg_data = encoding.decode_part(msg_data, to_fetch)


    if to_fetch == plain_part:
        msg_data = encoding.plaintext2html(msg_data)
    # elif content_type == 'text/html':
        # msg_data = encoding.clean_html(msg_data)

    return msg_data
