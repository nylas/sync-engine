from crispin import AuthFailure, TooManyConnectionsFailure
import sessionmanager
import logging as log
import encoding

# Note these are ALL auto-decorated with @tornado.gen.engine


def load_messages_for_folder(callback=None, **kwargs):
    folder_name= kwargs.get('folder_name', "Inbox")
    try:
        crispin_client = yield tornado.gen.Task(sessionmanager.get_crispin_from_email, 'mgrinich@gmail.com')
        log.info('fetching threads...')
        threads = crispin_client.fetch_messages(folder_name)
        callback([m.toJSON() for m in threads])

    except AuthFailure, e:
        log.error(e)
    except TooManyConnectionsFailure, e:
        log.error(e)
        callback(None)


def send_mail(callback=None, **kwargs):

    s = postel.SMTP('mgrinich@gmail.com', 
                    sessionmanager.get_access_token("mgrinich@gmail.com") )
    s.setup()
    s.send_mail("Test message", "Body content of test message!")
    s.quit()

    callback("OK")


def load_message_body_with_uid(callback=None, **kwargs):

    crispin_client = yield tornado.gen.Task(sessionmanager.get_crispin_from_email, 'mgrinich@gmail.com')

    msg_data = crispin_client.fetch_msg_body(kwargs['uid'], 
                                             kwargs['section_index'],
                                             folder='Inbox', )

    content_type = kwargs['content_type']
   
    # Let's decode...
    data_encoding = kwargs['encoding']
    msg_data = encoding.decode_data(msg_data, data_encoding)

    if content_type == 'text/plain':
        msg_data = encoding.plaintext2html(msg_data)
    elif content_type == 'text/html':
        msg_data = encoding.clean_html(msg_data)


    msg_data = encoding.webify_links(msg_data)
    callback(msg_data)



### Decorate all the above functions
import tornado.gen
import types
for k,v in globals().items():
    if isinstance(v, types.FunctionType):
        globals()[k] = tornado.gen.engine(v)
