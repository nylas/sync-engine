import email # TOFIX yuck

# import imaplib as imaplib_original
import auth
from email.header import decode_header
from imapclient import IMAPClient
from email.Parser import Parser
import time


base_gmail_url = 'https://mail.google.com/mail/b/' + auth.ACCOUNT + '/imap/'
HOST = 'imap.gmail.com'
ssl = True


server = None

# use decorators to make sure this happens? 
def connect():
    global server

    print 'Connecting to', auth.HOST
    try:
        server = IMAPClient(HOST, use_uid=True, ssl=ssl)
        server.oauth_login(base_gmail_url, 
                    auth.OAUTH_TOKEN, 
                    auth.OAUTH_TOKEN_SECRET, 
                    auth.CONSUMER_KEY, 
                    auth.CONSUMER_SECRET)
    except IMAPClient.Error, err:
        print 'Could not connect: ', e
        return
    print '    Connected.'


def setup():
    connect()
    select_folder("Inbox")


def list_folders():
    # TODO check failure case here
    global server

    if server == None:
        print "Why is there no server?"
        return

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

    print 'Selected folder %s with %d messages.' % (folder, select_info['EXISTS'])
    return select_info


# TODO this shit is broken
def create_draft(message_string):
    global server

    print 'Adding test draft...'
    server.append("[Gmail]/Drafts",
                str(email.message_from_string(message_string)))
    print 'Done!'

    # conn = imaplib.IMAP4_SSL('imap.gmail.com', port = 993)
    # psw = getpass.getpass("What's your password kiddo?: ")
    # print 'Logging in'
    # conn.login('mgrinich@gmail.com', psw)



def fetch_latest_message():
    global server

    messages = server.search(['NOT DELETED'])
    latest_email_uid = messages[-1]
    response = server.fetch(latest_email_uid, ['RFC822', 'X-GM-THRID', 'X-GM-MSGID'])
    return response[latest_email_uid]['RFC822']


def fetch_msg(msgid):
    global server

    # TODO actually use msgid here to look it up

    messages = server.search(['NOT DELETED'])
    latest_email_uid = messages[-1]
    response = server.fetch(latest_email_uid, ['RFC822', 'X-GM-THRID', 'X-GM-MSGID'])
    body = response[latest_email_uid]['RFC822']


    parser = Parser()
    message = parser.parsestr(body)


    msg_text = None
    content_type = None


    for part in message.walk():
        content_type = part.get_content_type()
        msg_text = part.get_payload(decode=True)

        if content_type == "text/html":
            break

        if part.get_content_type() == 'text/plain':
            msg_encoding = part.get_content_charset()

            # TODO check to see if we always have to do this? does it break stuff?
            msg_text = part.get_payload().decode('quoted-printable')
            # break

    return msg_text




def bodystructure_latest(self):
    pass


def gmail_url(self, UID):
    return "https://mail.google.com/mail/u/0/#inbox/" + hex(UID)


def fetch_all_udids(self):
    global server

    UIDs = server.search(['NOT DELETED'])
    return UIDs



def fetch_latest_5(self):
    global server

    messages = server.search(['NOT DELETED'])
    last_5 = messages[-5:]
    response = server.fetch(last_5, ['RFC822', 'X-GM-THRID', 'X-GM-MSGID'])
    return [ data['RFC822'] for (msgid, data) in response.iteritems() ]


def fetch_thread(self, thread_id):
    global server

    threads = server.search('X-GM-THRID ' + str(thread_id) )
    print threads


def fetch_all_messages(self, folder_name):
    pass



def fetch_headers(self, folder_name):
    global server

    select_info = self.select_folder(folder_name)
    UIDs = self.fetch_all_udids()

    query = 'BODY.PEEK[HEADER.FIELDS (TO CC FROM DATE SUBJECT)]'
    query_key = 'BODY[HEADER.FIELDS (TO CC FROM DATE SUBJECT)]'

    print 'Fetching all message headers:', query
    messages = server.fetch(UIDs, [query, 'X-GM-THRID'])
    print "   found %i messages." % len( messages.values() )


    parser = Parser()

    subjects = []

    for message_dict in messages.values():
        raw_header = message_dict[query_key]
        thread_id = message_dict['X-GM-THRID']

        message = parser.parsestr(raw_header)

        tos = message.get_all('to', [])
        ccs = message.get_all('cc', [])
        from_address = message.get_all('from', [])
        # from_name_decoded = decode_header(from_name)
        header_text = decode_header( message['Subject'] )
        default_encoding="ascii"
        header_sections = [unicode(text, charset or default_encoding)
                           for text, charset in header_text]

        # Headers will wrap when longer than 78 lines per RFC822_2
        subject = u"".join(header_sections).replace('\n\t', '').replace('\r\n', '')
        
        date_tuple = email.utils.parsedate_tz(message["Date"])
        sent_time = time.strftime("%I:%M %p - %b %d, %Y", date_tuple[:9])

        print 'From:', from_address[0]
        print 'To:', tos
        if len(ccs) > 0:
            print 'CC:', ccs
        print 'Date:', time.strftime("%c", date_tuple[:9])
        print 'THRID', thread_id
        print 'Subject', subject
        print


        subjects.append(subject)
    return subjects


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




if __name__ == "__main__":

    connect()   
    # select_info = m.select_folder(u'Awesome')

    # UIDs = m.fetch_all_udids()
    # latest_email_uid = UIDs[-1]
    # print '   Latest UID:', latest_email_uid
    # print '   Total UIDs: ', len(UIDs)

    # thread_id = message_dict['X-GM-THRID']

    # m.create_draft("Test hello world")

    # m.fetch_headers(u'Awesome')
    folders =  list_folders()

    other_folders = []
    print '\nSpecial mailboxes:'
    for f in folders:
        if u'\\AllMail' in f['flags']:
            print "    ALL MAIL --> ", f['name']
        elif u'\\Drafts' in f['flags']:
            print "    DRAFTS --> ", f['name']
        elif u'\\Important' in f['flags']:
            print "    IMPORTANT --> ", f['name']
        elif u'\\Sent' in f['flags']:
            print "    SENT --> ", f['name']
        elif u'\\Starred' in f['flags']:
            print "    STARRED --> ", f['name']
        elif u'\\Trash' in f['flags']:
            print "    TRASH --> ", f['name']
        else:
            other_folders.append(f)
    print '\Other mailboxes:'
    for f in other_folders:
        print "   ", f['name']
        
    print 'Unread counts:'
    for f in folders:
        if u'\\Noselect' in f['flags']: continue
        print f['flags']
        print "    " + f['name'] + '...', 
        print str(message_count(f['name']))


# Gmail IMAP    extensions
#   X-GM-LABELS
#   X-GM-MSGID
#   X-GM-THRID
#   X-GM-RAW
#   XLIST
