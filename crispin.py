import email # TOFIX yuck

# import imaplib as imaplib_original
import auth
from email.header import decode_header
from imapclient import IMAPClient
from email.Parser import Parser
import email.utils
import time
import datetime
import logging as log
import re

from webify import plaintext2html, fix_links, gravatar_url


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



def fetch_msg(msg_uid):
    global server
    response = server.fetch(msg_uid, ['RFC822', 'X-GM-THRID', 'X-GM-MSGID'])
    raw_response = response[msg_uid]['RFC822']


    new_msg = Message()

    parser = Parser()
    msg = parser.parsestr(raw_response)


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
                    for t in email.utils.getaddresses(addrs)]
        else:
            return dict(name = "undisclosed recipients", address = "")


    new_msg.to_contacts = parse_contact(['to', 'cc'])
    new_msg.from_contacts = parse_contact(['from'])

    subject = make_uni(msg['subject'])
    # Headers will wrap when longer than 78 lines per RFC822_2
    subject = subject.replace('\n\t', '')
    subject = subject.replace('\r\n', '')

    # Remove "RE" or whatever
    if subject[:4] == u'RE: ' or subject[:4] == u'Re: ' :
        subject = subject[4:]

    new_msg.subject = subject

    # TODO : upgrade to python3?
    # new_msg.date = email.utils.parsedate_to_datetime(msg["Date"])

    # date_tuple = email.utils.parsedate_tz(message["Date"])
    # sent_time = time.strftime("%b %m, %Y &mdash; %I:%M %p", date_tuple[:9])

    time_epoch = time.mktime( email.utils.parsedate_tz(msg["Date"])[:9] )
    new_msg.date = datetime.datetime.fromtimestamp(time_epoch)

    log.info('To: %s' % new_msg.to_contacts)
    log.info('From: %s' % new_msg.from_contacts)
    log.info('Subject: %s' % new_msg.subject)
    log.info('Date: %s' % new_msg.date.strftime('%b %m, %Y %I:%M %p') )

    # log.info('Date: %s' % new_msg.date )


    msg_text = None
    content_type = None

    maintype = msg.get_content_maintype()
    if maintype == 'multipart':
        for part in msg.get_payload():
            if part.get_content_maintype() == 'text':
                msg_text = part.get_payload(decode=True)
                content_type = part.get_content_type()
    elif maintype == 'text':
        msg_text = msg.get_payload(decode=True)
        content_type = msg.get_content_type()
    else:
        log.error("Message doesn't have text Content-Type: %s" % msg)

        # msg_text = quopri.decodestring(msg_text)


    # My old way of doing this

    # for part in message.walk():
    #     content_type = part.get_content_type()
    #     if content_type == "text/html":
    #         msg_text = part.get_payload(decode=True)
    #         break
    #     if part.get_content_type() == 'text/plain':
    #         continue
    #         # break

    if msg_text == None:
        log.error("Couldn't find message text! %s" % msg)
        return ""

    msg_text = msg_text.decode('iso-8859-1').encode('utf8')


    # TODO: This doesn't always work right.
    # This is so broken
    # msg_text = trim_quoted_text(msg_text, content_type)

    if content_type == 'text/plain':
        msg_text = plaintext2html(msg_text)

    msg_text = fix_links(msg_text)

    new_msg.body_text = msg_text

    return new_msg





def fetch_all_udids(self):
    global server
    UIDs = server.search(['NOT DELETED'])
    return UIDs



def fetch_thread(self, thread_id):
    global server
    threads = server.search('X-GM-THRID %s' % str(thread_id) )
    print threads



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
