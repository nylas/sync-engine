from email import message_from_string
import email.utils as email_utils
from email.Parser import Parser
from email.header import decode_header
from email.Iterators import typed_subpart_iterator
from imapclient import IMAPClient
import time
import datetime
import logging as log

import auth
from webify import plaintext2html, fix_links, trim_quoted_text, trim_subject, gravatar_url

from models import Message, MessageThread, MessageBodyPart


server = None



# BODY.PEEK[HEADER]
# X-GM-THRID
# X-GM-MSGID
# X-GM-LABELS
# BODY.PEEK[HEADER.FIELDS (Message-Id)]
# BODY.PEEK[HEADER.FIELDS (From)]
# ENVELOPE
# RFC822.SIZE
# UID
# FLAGS
# INTERNALDATE
# X-GM-THRID
# X-GM-MSGID
# X-GM-LABELS



# use decorators to make sure this happens? 
def connect():
    global server
    log.info('Connecting to %s ...' % auth.IMAP_HOST,)

    try:
        server.noop()
        log.info('Already connected to host.')
        return True
    except Exception, e:
        log.info('No active connection. Opening connection...')

    try:
        server = IMAPClient(auth.IMAP_HOST, use_uid=True, ssl=auth.SSL)
        server.oauth_login(auth.BASE_GMAIL_IMAP_URL, 
                    auth.OAUTH_TOKEN, 
                    auth.OAUTH_TOKEN_SECRET, 
                    auth.CONSUMER_KEY, 
                    auth.CONSUMER_SECRET)
    except Exception, e:
        log.error("IMAP connection error: %s", e)
        return False

    log.info('Connection successful.')
    return True


def list_folders():
    global server
    try:
        resp = server.xlist_folders()
    except Exception, e:
        raise e
    return [dict(flags = f[0], delimiter = f[1], name = f[2]) for f in resp]
    

def all_mail_folder_name():
    folders =  list_folders()
    for f in folders:
        if u'\\AllMail' in f['flags']:
            return f['name']


def get_special_folder(special_folder):
    # TODO return folders for stuff like All Mail, Drafts, etc. which may
    # be localized names. Use the flags, such as u'\\AllMail' or u'\\Important'

    # Some old example code

    # folders =  list_folders()
    # other_folders = []
    # print '\nSpecial mailboxes:'
    # for f in folders:
    #     if u'\\AllMail' in f['flags']:
    #         print "    ALL MAIL --> ", f['name']
    #     elif u'\\Drafts' in f['flags']:
    #         print "    DRAFTS --> ", f['name']
    #     elif u'\\Important' in f['flags']:
    #         print "    IMPORTANT --> ", f['name']
    #     elif u'\\Sent' in f['flags']:
    #         print "    SENT --> ", f['name']
    #     elif u'\\Starred' in f['flags']:
    #         print "    STARRED --> ", f['name']
    #     elif u'\\Trash' in f['flags']:
    #         print "    TRASH --> ", f['name']
    #     else:
    #         other_folders.append(f)
    # print '\Other mailboxes:'
    # for f in other_folders:
    #     print "   ", f['name']
    pass


def message_count(folder):
    global server
    select_info = server.select_folder(folder, readonly=True)
    return int(select_info['EXISTS'])


def select_folder(folder):
    global server
    select_info = server.select_folder(folder, readonly=True)
    # Format of select_info
    # {'EXISTS': 3597, 'PERMANENTFLAGS': (), 
    # 'UIDNEXT': 3719, 
    # 'FLAGS': ('\\Answered', '\\Flagged', '\\Draft', '\\Deleted', '\\Seen', '$Pending', 'Junk', 'NonJunk', 'NotJunk', '$Junk', 'Forwarded', '$Forwarded', 'JunkRecorded', '$NotJunk'), 
    # 'UIDVALIDITY': 196, 'READ-ONLY': [''], 'RECENT': 0}
    log.info('Selected folder %s with %d messages.' % (folder, select_info['EXISTS']) )
    return select_info

def select_allmail_folder():
    return select_folder(all_mail_folder_name())


# TODO this shit is broken
def create_draft(message_string):
    global server

    log.info('Adding test draft..')
    server.append("[Gmail]/Drafts",
                str(email.message_from_string(message_string)))
    log.info("Done creating test draft.")



def latest_message_uid():
    global server
    messages = server.search(['NOT DELETED'])
    return messages[-1]


def fetch_latest_message():
    global server
    latest_email_uid = latest_message_uid();
    response = server.fetch(latest_email_uid, ['RFC822', 'X-GM-THRID', 'X-GM-MSGID'])
    return response[latest_email_uid]['RFC822']


def parse_main_headers(msg):
    new_msg = Message()

    def make_uni(txt, default_encoding="ascii"):
        return u"".join([unicode(text, charset or default_encoding)
                   for text, charset in decode_header(txt)]) 

    def parse_contact(headers):
        # Works with both strings and lists
        try: headers += []
        except: headers = [headers] 

        # combine and flatten header values
        addrs = reduce(lambda x,y: x+y, [msg.get_all(a, []) for a in headers])
        
        if len(addrs) > 0:
            return [ dict(name = make_uni(t[0]),
                          address=make_uni(t[1]))
                    for t in email_utils.getaddresses(addrs)]
        else:
            return [ dict(name = "undisclosed recipients", address = "") ]

    new_msg.to_contacts = parse_contact(['to', 'cc'])
    new_msg.from_contacts = parse_contact(['from'])

    subject = make_uni(msg['subject'])
    new_msg.subject = trim_subject(subject)

    time_epoch = time.mktime( email_utils.parsedate_tz(msg["Date"])[:9] )
    new_msg.date = datetime.datetime.fromtimestamp(time_epoch)

    return new_msg

def parse_body(msg, new_msg = Message()):

    msg_text = ""
    content_type = None

    def get_charset(message, default="ascii"):
        if message.get_content_charset(): return message.get_content_charset()
        if message.get_charset(): return message.get_charset()
        return default

    if msg.is_multipart():
        #get the plain text version only
        text_parts = [part for part in typed_subpart_iterator(msg, 'text', 'plain')]
        body = []
        for part in text_parts:
            charset = get_charset(part, get_charset(msg))
            body.append( unicode(part.get_payload(decode=True), charset, "replace") )
            content_type = part.get_content_type()
        msg_text = u"\n".join(body).strip()

    else: # if it is not multipart, the payload will be a string
          # representing the message body
        body = unicode(msg.get_payload(decode=True), get_charset(msg), "replace")
        content_type = msg.get_content_type()
        msg_text = body.strip() # removes whitespace characters

    if len(msg_text) == 0:
        log.error("Couldn't find message text. Content-type: %s" % content_type)


    # Don't think I need to do this anymore now that the above is creating
    # unicode strings based on content encoding...
    # msg_text = msg_text.decode('iso-8859-1').encode('utf8')

    # TODO: Fuck this is so broken for HTML mail
    msg_text = trim_quoted_text(msg_text, content_type)

    if content_type == 'text/plain':
        msg_text = plaintext2html(msg_text)

    msg_text = fix_links(msg_text)


    new_msg.body_text = msg_text
    return new_msg



def fetch_msg(msg_uid):
    msg_uid = long(msg_uid)
    global server

    log.info("Fetching message. UID: %i" % msg_uid)
    
    response = server.fetch(str(msg_uid), ['RFC822', 'X-GM-THRID', 'X-GM-MSGID'])
    
    if len(response.keys()) == 0:
        log.error("No response for msg query. msg_id = %s", msg_uid)
        return None

    raw_response = response[msg_uid]['RFC822']
    log.info("Received response. Size: %i" % len(raw_response))

    msg = Parser().parsestr(raw_response)

    # headers
    new_msg = parse_main_headers(msg)  # returns Message()

    # body
    new_msg = parse_body(msg, new_msg)

    log.info('To: %s' % new_msg.to_contacts)
    log.info('From: %s' % new_msg.from_contacts)
    log.info('Subject: %s' % new_msg.subject)
    log.info('Date: %s' % new_msg.date.strftime('%b %m, %Y %I:%M %p') )

    return new_msg


def fetch_all_udids():
    global server
    UIDs = server.search(['NOT DELETED'])
    return UIDs


def fetch_thread(thread_id):
    global server
    threads_msg_ids = server.search('X-GM-THRID %s' % str(thread_id) )
    return threads_msg_ids


def fetch_threads(folder_name):

    threads = {}
    msgs = fetch_headers(folder_name)

    for m in msgs:
        if m.thread_id not in threads.keys():
            new_thread = MessageThread()
            new_thread.thread_id = m.thread_id
            threads[m.thread_id] = new_thread

        t = threads[m.thread_id]
        t.messages.append(m) # not all, only messages in folder_name


    select_info = select_folder( all_mail_folder_name() )
    for t in threads.values():
        log.info("Fetching thread with ID: %s" % t.thread_id)
        t.message_ids = fetch_thread(t.thread_id) # all

    return threads.values()



def fetch_headers(folder_name):
    global server

    query = 'BODY.PEEK[HEADER.FIELDS (TO CC FROM DATE SUBJECT)]'
    query_key = 'BODY[HEADER.FIELDS (TO CC FROM DATE SUBJECT)]'

    log.info("Fetching message headers. Query: %s" % query)
    select_info = select_folder(folder_name)
    UIDs = fetch_all_udids()

    log.info("Fetching message headers. Query: %s" % query)
    messages = server.fetch(UIDs, [query, 'X-GM-THRID'])
    log.info("found %i messages." % len(messages.values()))

    parser = Parser()
    new_messages = []

    for message_dict in messages.values():
        raw_header = message_dict[query_key]
        msg = parser.parsestr(raw_header)

        # headers
        new_msg = parse_main_headers(msg)  # returns Message()
        new_msg.thread_id = message_dict['X-GM-THRID']

        log.info("adding: %s" % new_msg.subject)

        new_messages.append(new_msg)

        new_msg = None

    return new_messages





        

def fetch_MessageBodyPart(UIDs):

    if isinstance(UIDs, int ):
        UIDs = [str(UIDs)]
    elif isinstance(UIDs, basestring):
        UIDs = [UIDs]


    global server
    query = 'ENVELOPE BODY INTERNALDATE'

    # envelope gives relevant headers and is really fast in practice
    # RFC822.HEADER will give *all* of the headers, and is probably slower? // TODO 
    # query = 'RFC822.HEADER BODY'
    # query = 'FLAGS UID RFC822.SIZE INTERNALDATE BODY.PEEK[HEADER] BODY'

    log.info("Fetching messages with query: %s" % query )
    messages = server.fetch(UIDs, [query, 'X-GM-THRID'])
    log.info("  ...found %i messages." % len(messages.values()))


    bodystructure_parts = []


    for m in messages.keys():
        
        bodystructure = messages[m]['BODY']
        if bodystructure.is_multipart:

            parts = bodystructure[0]
            for i in xrange(len(parts)):
                part = parts[i]
                # Sometimes one of the body parts is actually something weird like 
                # Content-Type: multipart/alternative, so you have to loop though them
                # individually. I think email.parser takes care of this when you fetch
                # the actual body content, but I have to do it here for the BODYSTRUCTURE
                # response. 

                # recurisve creator since these might be nested
                # pass the index so we can append subindicies
                # Note: this shit might break but it works for now...
                def make_obj(p, i):
                    if not isinstance(p[0], basestring):
                        for x in range(len(part) - 1): # The last one is the label
                            if len(i) > 0: index = i+'.'+ str(x+1)
                            else: index = str(x+1)
                            make_obj(p[x], index)
                    else:
                        if len(i) > 0: index = i+'.1'
                        else: index = '1'
                        bodystructure_parts.append(MessageBodyPart(p,i))
                make_obj(part, str(i+1))

        else:
            bodystructure_parts.append(MessageBodyPart(bodystructure, '1'))

    return bodystructure_parts
    

def main():


    # log.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
    log.basicConfig(format='%(message)s', level=log.DEBUG)
    # log.basicConfig(level=log.DEBUG)

    if not ( connect() ):
        print "Couldn't connect. :("
        return

    select_info = select_folder("Inbox") 
    UIDs = fetch_all_udids()

    # select_info = select_folder("Inbox") 
    # sadie_msg_uid = '114164' # '394102' in All Mail 
    # UIDs = [sadie_msg_uid]

    # select_allmail_folder()
    # regular_thread_uid = '395760'
    # UIDs = [regular_thread_uid]


    bodystructs = fetch_MessageBodyPart(UIDs)


    for b in bodystructs:
        print b


if __name__ == "__main__":
    main()
