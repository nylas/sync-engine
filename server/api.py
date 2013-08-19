from crispin import AuthFailure, TooManyConnectionsFailure
import sessionmanager
import logging as log
import encoding

import json
import postel
from bson import json_util



from sqlalchemy import *
from models import db_session, Base, MessageMeta


def messages_for_folder(folder_name="Inbox", user=None):
    assert user, "Must have user for operation"


    try:
        # crispin_client = sessionmanager.get_crispin_from_email(email_address)
        # log.info('fetching threads...')

        # threads = crispin_client.fetch_messages(folder_name)

        existing_msgs = db_session.query(MessageMeta).filter(MessageMeta.in_inbox == True).all()
        # Fixes serializing date.datetime
        return json.dumps([m.client_json() for m in existing_msgs],
                           default=json_util.default)

    except AuthFailure, e:
        log.error(e)
    except TooManyConnectionsFailure, e:
        log.error(e)
        return None


def send_mail(email_address, **kwargs):

    user_obj = sessionmanager.get_user(email_address)
    s = postel.SMTP(user_obj.g_email,
                    user_obj.g_access_token)

    s.setup()
    s.send_mail("Test message", "Body content of test message!")
    s.quit()
    return "OK"




def data_with_id(data_id, user=None):

    log.info('in data_with_id')

    existing_msgs_query = db_session.query(MessageMeta).filter(MessageMeta.g_msgid == data_id)

    log.info(existing_msgs_query)

    meta = existing_msgs_query.all()

    print 'meta', meta

    assert len(meta) == 1
    m = meta[0]

    print m

    crispin_client = sessionmanager.get_crispin_from_email('mgrinich@gmail.com')

    msg_data = crispin_client.fetch_msg_body(m.uid, '1')


    # TODO need to decode it here

    return msg_data



def load_message_body_with_uid(uid, section_index, data_encoding, content_type, email_address):

    crispin_client = sessionmanager.get_crispin_from_email(email_address)

    msg_data = crispin_client.fetch_msg_body(uid,
                                             section_index,
                                             folder='Inbox', )

    msg_data = encoding.decode_data(msg_data, data_encoding)

    if content_type == 'text/plain':
        msg_data = encoding.plaintext2html(msg_data)
    # elif content_type == 'text/html':
        # msg_data = encoding.clean_html(msg_data)


    msg_data = encoding.webify_links(msg_data)


    import base64

    return base64.b64encode(msg_data)
