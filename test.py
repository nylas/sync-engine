import oauth2 as oauth
import email
import oauth2.clients.smtp as smtplib
import oauth2.clients.imap as imaplib
import time
import re
import imaplib as imaplib_original
from email.Parser import Parser


# from sendreceive import Awesomemail

# am = AwesomeMail()
# am.setup()
# # am.create_draft()
# print am.fetch_latest_message()

# ms = MailSender()
# ms.setup()
# ms.send_mail('hey olof', 'Dont work too hard.')

import auth

base_gmail_url = 'https://mail.google.com/mail/b/' + auth.account



url = base_gmail_url + "/imap/"

obj = imaplib.IMAP4_SSL('imap.googlemail.com')            
# obj.debug = 4 
result = obj.authenticate(url, auth.consumer, auth.token)

if result != None: 
    print 'Error: ', result
    raise Exception(result)




obj.select('Inbox')



# result, data = mail.uid('fetch', uid, '(X-GM-THRID X-GM-MSGID)')


def get_headers_only():

    resp, data = obj.uid('FETCH', '1:*' , '(RFC822.HEADER)')

    if resp != "OK":
        raise Exception('Server returned something else. 284902y34234')
    messages = [data[i][1].strip() + "\r\nSize:" + data[i][0].split()[4] + "\r\nUID:" + data[i][0].split()[2]  for i in xrange(0, len(data), 2)]



    for msg in messages:

        msg_str = email.message_from_string(msg)
        message_id = msg_str.get('Message-ID')

        print msg_str.get('UID')
        print msg_str.get('Message-ID')
        print msg_str.get('Size')



def get_mailbox_uids():
    
    status, data = obj.uid('search', None, "ALL") # search and return uids instead
    results = data[0].split()
    print "IMAP Server returned " + str(len(results)) + " results"
    # pp = pprint.PrettyPrinter(indent=4)
    # print pp.pformat([parse_email(fetch_email(mail, i))['headers'] for i in results])
    return results




def get_header_key(uid):

    result, data = obj.uid('fetch', uid, '(BODY[HEADER.FIELDS (DATE SUBJECT)]])')

    return data


# get_headers_subjects()
uids =  get_mailbox_uids()

for uid in uids:
    print get_header_key(uid)
