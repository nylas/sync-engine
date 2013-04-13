from email import message_from_string
import email.utils as email_utils
from email.Parser import Parser

# import imaplib as imaplib_original
import auth
from email.header import decode_header
from email.Iterators import typed_subpart_iterator
from imapclient import IMAPClient
import time
import datetime
import logging as log

from webify import plaintext2html, fix_links, trim_quoted_text, gravatar_url


base_gmail_url = 'https://mail.google.com/mail/b/' + auth.ACCOUNT + '/imap/'
HOST = 'imap.gmail.com'
ssl = True


server = None


# { 
# tos: [ <Contacts>, ... ]
# from: 
#     [ <Contact> name, address, ... ]
# headers:
#     { 'someheader', value}

# body-text { 'content-type', bodyvalue}
#     >>> somehow have resource keys in body-text

# resources {'file-key', value}

# }


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




class Message():
    def __init__(self):
        self.to_contacts = []
        self.from_contacts = None
        self.subject = None
        self.date = None
        self.body_text = {}

        self.thread_id = None
        self.size = None
        self.uid = None

    def gravatar(self):
        return gravatar_url(self.from_contacts[0]['address'])

    def gmail_url(self):
        if not self.uid: return
        # http://mail.google.com/mail?account_id=ACCOUNT_ID_HERE&message_id=MESSAGE_ID_HERE&view=conv&extsrc=atom
        return "https://mail.google.com/mail/u/0/#inbox/" + hex(self.uid)




# use decorators to make sure this happens? 
def connect():
    global server
    log.info('Connecting to %s ...' % auth.HOST,)

    try:
        server.noop()
        log.info('Already connected to host.')
        return True
    except Exception, e:
        log.info('No active connection. Opening connection...')

    try:
        server = IMAPClient(HOST, use_uid=True, ssl=ssl)
        server.oauth_login(base_gmail_url, 
                    auth.OAUTH_TOKEN, 
                    auth.OAUTH_TOKEN_SECRET, 
                    auth.CONSUMER_KEY, 
                    auth.CONSUMER_SECRET)
    except IMAPClient.Error, err:
        log.error("Could not connect. %s", e)
        return False

    log.info('Connection successful.')
    return True


def setup():
    connect()
    select_folder("Inbox")


def list_folders():
    global server
    try:
        resp = server.xlist_folders()
    except Exception, e:
        raise e
    return [dict(flags = f[0], delimiter = f[1], name = f[2]) for f in resp]
    

def message_count(folder):
    global server
    select_info = server.select_folder(folder, readonly=True)
    return int(select_info['EXISTS'])


def select_folder(folder):
    global server

    # TOFIX catch exception here
    select_info = server.select_folder(folder, readonly=True)

    # Format of select_info
    # {'EXISTS': 3597, 'PERMANENTFLAGS': (), 
    # 'UIDNEXT': 3719, 
    # 'FLAGS': ('\\Answered', '\\Flagged', '\\Draft', '\\Deleted', '\\Seen', '$Pending', 'Junk', 'NonJunk', 'NotJunk', '$Junk', 'Forwarded', '$Forwarded', 'JunkRecorded', '$NotJunk'), 
    # 'UIDVALIDITY': 196, 'READ-ONLY': [''], 'RECENT': 0}
    log.info('Selected folder %s with %d messages.' % (folder, select_info['EXISTS']) )
    return select_info


# TODO this shit is broken
def create_draft(message_string):
    global server

    print 'Adding test draft...'
    server.append("[Gmail]/Drafts",
                str(email.message_from_string(message_string)))
    print 'Done!'



def latest_message_uid():
    global server
    messages = server.search(['NOT DELETED'])
    return messages[-1]


def fetch_latest_message():
    global server
    latest_email_uid = latest_message_uid();
    response = server.fetch(latest_email_uid, ['RFC822', 'X-GM-THRID', 'X-GM-MSGID'])
    return response[latest_email_uid]['RFC822']


def parse_main_headers(msg, new_msg = Message()):
    # new_msg = Message()

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
    # Headers will wrap when longer than 78 lines per RFC822_2
    subject = subject.replace('\n\t', '').replace('\r\n', '')

    # Remove "RE" or whatever
    if subject[:4] == u'RE: ' or subject[:4] == u'Re: ' :
        subject = subject[4:]

    new_msg.subject = subject

    # TODO : upgrade to python3?
    # new_msg.date = email_utils.parsedate_to_datetime(msg["Date"])

    # date_tuple = email_utils.parsedate_tz(message["Date"])
    # sent_time = time.strftime("%b %m, %Y &mdash; %I:%M %p", date_tuple[:9])

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
    global server

    log.info("Fetching message. UID: %i" % msg_uid)
    response = server.fetch(msg_uid, ['RFC822', 'X-GM-THRID', 'X-GM-MSGID'])
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


def fetch_thread(self, thread_id):
    global server
    threads = server.search('X-GM-THRID %s' % str(thread_id) )
    print threads



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
    subjects = []

    for message_dict in messages.values():
        raw_header = message_dict[query_key]
        thread_id = message_dict['X-GM-THRID']

        msg = parser.parsestr(raw_header)

        # headers
        new_msg = parse_main_headers(msg)  # returns Message()
        subjects.append(new_msg.subject)

    return subjects




def main():

    log.basicConfig(level=log.DEBUG)

    if not ( connect() ):
        print "Couldn't connect. :("
        return

    setup()

    uid = latest_message_uid()
    msg = fetch_msg(uid)

    print msg.subject


    # select_info = m.select_folder(u'Awesome')

    # UIDs = m.fetch_all_udids()
    # latest_email_uid = UIDs[-1]
    # print '   Latest UID:', latest_email_uid
    # print '   Total UIDs: ', len(UIDs)

    # thread_id = message_dict['X-GM-THRID']

    # m.create_draft("Test hello world")

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
        
    # print 'Unread counts:'
    # for f in folders:
    #     if u'\\Noselect' in f['flags']: continue
    #     print f['flags']
    #     print "    " + f['name'] + '...', 
    #     print str(message_count(f['name']))



if __name__ == "__main__":
    main()
