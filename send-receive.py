import oauth2 as oauth
import email
import oauth2.clients.smtp as smtplib
import oauth2.clients.imap as imaplib

import re


# TODO decode headers
# from email.header import decode_header
# value, charset = decode_header(string_to_be_decoded)



# Get oauth keys:
# python xoauth.py --generate_oauth_token --user=testing.oauth.1@gmail.com

# Enter verification code: HNYJNhY2rBCMg0pA1grbyaK2
# oauth_token: 1/LG4tUierWCflZoMoBk8nL7Kev7mITub9-bAVXAJlDIc
# oauth_token_secret: 2Jh36SZR39MSChO9OVD2b7vV

# Set up your Consumer and Token as per usual. Just like any other
# three-legged OAuth request.
consumer = oauth.Consumer('anonymous', 'anonymous')

token = oauth.Token('1/LG4tUierWCflZoMoBk8nL7Kev7mITub9-bAVXAJlDIc', 
    '2Jh36SZR39MSChO9OVD2b7vV')


account = 'mgrinich@gmail.com'

base_gmail_url = 'https://mail.google.com/mail/b/' + account



def sendMail(msg_subject, msg_body):

    if message == None: return

    url = base_gmail_url + "/smtp/"

    #conn = smtplib.SMTP('smtp.googlemail.com', 587)
    conn = smtplib.SMTP('smtp.gmail.com', 587)

    #conn.debug = 4 
    conn.set_debuglevel(True)

    conn.ehlo()
    conn.starttls()
    conn.ehlo()

    conn.authenticate(url, consumer, token)

    header = 'To:mgrinich+emailtest@gmail.com\n' + 'From: mgrinich@gmail.com\n' + 'Subject:' + msg_subject + '\n'

    msg = header + '\n' + msg_body + '\n\n'

    conn.sendmail('mgrinich+emailtest@gmail.com', 'mgrinich+emailtest@gmail.com', msg)




def list_mailboxes():

    url = base_gmail_url + "/imap/"
    conn = imaplib.IMAP4_SSL('imap.googlemail.com')
    conn.debug = 4 

    conn.authenticate(url, consumer, token)

    # Once authenticated everything from the impalib.IMAP4_SSL class will 
    # work as per usual without any modification to your code.
    conn.select('Inbox')

    raw_mailboxes = conn.list()[1]

    my_mailboxes = [box.split(' "/" ')[1][1:-1] for box in raw_mailboxes]

    return my_mailboxes


def fetch_latest_message():
    

    url = base_gmail_url + "/imap/"
    conn = imaplib.IMAP4_SSL('imap.googlemail.com')
    conn.debug = 4 

    conn.authenticate(url, consumer, token)

    conn.select('Inbox')

    # result, data = conn.search(None, "ALL")
    result, data = conn.uid('search', None, "ALL") # search and return uids instead


    ids = data[0] # data is a list.
    id_list = ids.split() # ids is a space separated string
    latest_email_uid = id_list[-1] # get the latest

    # result, data = conn.fetch(latest_email_id, "(RFC822)") # fetch the email body (RFC822) for the given ID
    result, data = conn.uid('fetch', latest_email_uid, '(RFC822)')
    
    raw_email = data[0][1]

    return raw_email


def latest_email_uids(how_many = 1):
    url = base_gmail_url + "/imap/"
    conn = imaplib.IMAP4_SSL('imap.googlemail.com')
    conn.debug = 4 

    conn.authenticate(url, consumer, token)

    conn.select('Inbox')

    # result, data = conn.search(None, "ALL")
    result, data = conn.uid('search', None, "ALL") # search and return uids instead

    ids = data[0] # data is a list.
    id_list = ids.split() # ids is a space separated string
    return id_list[ - how_many :] # get the latest




def fetch_messages(uids):

    if len(uids) < 1: return

    url = base_gmail_url + "/imap/"
    conn = imaplib.IMAP4_SSL('imap.googlemail.com')
    conn.debug = 4 

    conn.authenticate(url, consumer, token)

    conn.select('Inbox')

    uids = [str(x) for x in uids]

    uids_cat = ",".join(uids)

    print 'catted:', uids_cat

    # result, data = conn.uid('fetch', uids_cat, '(X-GM-THRID X-GM-MSGID)')

    # result, data = conn.uid('fetch', uids_cat, '(X-GM-THRID X-GM-MSGID)')
    result, data = conn.uid('fetch', uids_cat, 'RFC822')


    if result != 'OK':
        print 'WTF something went wrong error'
        return

    print data

    # re.search('X-GM-THRID (?P<X-GM-THRID>\d+) X-GM-MSGID (?P<X-GM-MSGID>\d+)', data[0]).groupdict()
    # this becomes an organizational lifesaver once you have many results returned.


def fetch_message(mailbox_name, uid):

    url = base_gmail_url + "/imap/"

    conn = imaplib.IMAP4_SSL('imap.googlemail.com')
    conn.debug = 4

    conn.authenticate(url, consumer, token)

    # Once authenticated everything from the impalib.IMAP4_SSL class will 
    # work as per usual without any modification to your code.
    conn.select(mailbox_name)

    status, data = conn.uid('fetch', uid, 'RFC822')

    return data



latest = latest_email_uids(10)    
print 'Latest UIDs: ', latest

data = fetch_messages(latest)



# for uid in latest:
#     data = fetch_message('Inbox', uid)
#     print '---------------------\n', data