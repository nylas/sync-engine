from crispin import AuthFailure, TooManyConnectionsFailure
import sessionmanager
import logging as log
import encoding

import json


from bson import json_util
import json



def messages_for_folder(email_address, folder_name="Inbox"):
    # folder_name= kwargs.get('folder_name', "Inbox")
    try:
        crispin_client = sessionmanager.get_crispin_from_email(email_address)
        log.info('fetching threads...')

        threads = crispin_client.fetch_messages(folder_name)

        # Fixes serializing date.datetime
        return json.dumps(threads, default=json_util.default)


    except AuthFailure, e:
        log.error(e)
    except TooManyConnectionsFailure, e:
        log.error(e)
        return None




def send_mail(email_address, **kwargs):

    s = postel.SMTP(email_address,
                    sessionmanager.get_access_token(email_address) )
    s.setup()
    s.send_mail("Test message", "Body content of test message!")
    s.quit()

    return "OK"


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
