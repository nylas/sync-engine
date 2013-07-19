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
   
    import webify
    import quopri
    import bleach
    from bs4 import BeautifulSoup


    # Let's decode...

    data_encoding = kwargs['encoding']


    msg_data = encoding.decode_data(msg_data, data_encoding)


    if content_type == 'text/plain':
        msg_data = webify.plaintext2html(msg_data)

    elif content_type == 'text/html':

        soup = BeautifulSoup(msg_data)

        # Bad elements
        for s in soup('head'): s.extract()
        for s in soup('style'): s.extract()
        for s in soup('script'): s.extract()
        for m in soup('html'): m.replaceWithChildren()
        for m in soup('body'): m.replaceWithChildren()

        # for match in soup.findAll('body'):
        #     print 'MATCHED!'
        #     match.replaceWithChildren()
        #     # new_tag = soup.new_tag('div')
        #     # new_tag.contents = b.contents
        #     # b.replace_with(new_tag)

        msg_data = str(soup)


        # msg_data = tornado.escape.linkify(msg_data, shorten=True)

    msg_data = bleach.linkify(msg_data)
    # msg_data = bleach.clean(msg_data, strip=True)
    # msg_data = webify.fix_links(msg_data)

    # Shorten URLs to 30 characters
    soup = BeautifulSoup(msg_data)
    for a in soup.findAll('a'):
        a['target'] = "_blank"
        try:
            if a.contents[0] == a['href']:
                a.string = a['href'][:30] + '&hellip;'
            a['title'] = a['href']
        except Exception, e:
            log.info("Found anchor without href. Contents: %s" % a)
            pass
    msg_data = str(soup)

    callback(msg_data)



### Decorate all the above functions
import tornado.gen
import types
for k,v in globals().items():
    if isinstance(v, types.FunctionType):
        globals()[k] = tornado.gen.engine(v)
