import oauth2 as oauth
import email
import oauth2.clients.smtp as smtplib
import oauth2.clients.imap as imaplib
import time
import re
import imaplib as imaplib_original

import auth

base_gmail_url = 'https://mail.google.com/mail/b/' + auth.account


class AwesomeMail():
    """docstring for AwesomeMail"""


    def __init__(self):
    #     # super(AwesomeMail, self).__init__()
        self.conn = None


    def setup(self):
        url = base_gmail_url + "/imap/"

        self.conn = imaplib.IMAP4_SSL('imap.googlemail.com')            
        self.conn.debug = 4 
        result = self.conn.authenticate(url, auth.consumer, auth.token)

        print 'Result ', result

        self.conn.select('Inbox', readonly=True)



    def list_mailboxes(self):

        # Once authenticated everything from the impalib.IMAP4_SSL class will 
        # work as per usual without any modification to your code.

        raw_mailboxes = self.conn.list()[1]

        my_mailboxes = [box.split(' "/" ')[1][1:-1] for box in raw_mailboxes]

        return my_mailboxes


    def fetch_message_UIDs(self):
        
        # result, data = self.conn.search(None, "ALL")
        result, data = self.conn.uid('search', None, "ALL") # search and return uids instead

        ids = data[0] # data is a list.
        id_list = ids.split() # ids is a space separated string
        return id_list


    def fetch_latest_message(self):

        # result, data = self.conn.search(None, "ALL")
        result, data = self.conn.uid('search', None, "ALL") # search and return uids instead

        ids = data[0] # data is a list.
        id_list = ids.split() # ids is a space separated string
        latest_email_uid = id_list[-1] # get the latest

        # result, data = self.conn.fetch(latest_email_id, "(RFC822)") # fetch the email body (RFC822) for the given ID
        result, data = self.conn.uid('fetch', latest_email_uid, '(RFC822)')
        
        # TODO check result

        raw_email = data[0][1]

        return raw_email



    def get_labels(self, uid):
        
        t, d = imapconn.uid('FETCH', uid, '(X-GM-LABELS)')
        t, d = imapconn.fetch(uid, '(X-GM-LABELS)')


    def latest_email_uids(self,how_many = 1):


        # result, data = self.conn.search(None, "ALL")
        result, data = self.conn.uid('search', None, "ALL") # search and return uids instead

        ids = data[0] # data is a list.
        id_list = ids.split() # ids is a space separated string
        return id_list[ - how_many :] # get the latest




    def fetch_messages(self, uids):

        if len(uids) < 1: return


        uids = [str(x) for x in uids]

        uids_cat = ",".join(uids)

        print 'catted:', uids_cat

        # result, data = self.conn.uid('fetch', uids_cat, '(X-GM-THRID X-GM-MSGID)')

        # result, data = self.conn.uid('fetch', uids_cat, '(X-GM-THRID X-GM-MSGID)')
        result, data = self.conn.uid('fetch', uids_cat, 'RFC822')


        if result != 'OK':
            raise Exception("Server returned error on fetching UIDs:", uids)
            return

        print '\n\n\n\n\n\n\n\n'

        data = data[::2]

        for message in data:
            raw_meta, raw_body = message
            print raw_meta


        # re.search('X-GM-THRID (?P<X-GM-THRID>\d+) X-GM-MSGID (?P<X-GM-MSGID>\d+)', data[0]).groupdict()
        # this becomes an organizational lifesaver once you have many results returned.


    def fetch_message(self, mailbox_name, uid):

        self.conn.select(mailbox_name)

        # fetch the email body (RFC822) for the given ID
        status, data = self.conn.uid('fetch', fetch_ids, '(BODY.PEEK[])')


        return data


    def create_draft(self):


        self.conn.select('[Gmail]/Drafts')

        print 'Adding test draft'

        self.conn.append("[Gmail]/Drafts", '',
                    imaplib_original.Time2Internaldate(time.time()),
                    
                    str(email.message_from_string('TEST')))

        print 'Done!'





class MailSender(object):

    def __init__(self):
        self.conn = None

    def setup(self):

        url = base_gmail_url + "/smtp/"

        self.conn = smtplib.SMTP('smtp.googlemail.com', 587)
        #conn = smtplib.SMTP('smtp.gmail.com', 587)

        #conn.debug = 4 
        self.conn.set_debuglevel(True)

        self.conn.ehlo()
        self.conn.starttls()
        self.conn.ehlo()

        self.conn.authenticate(url, consumer, token)


    def send_mail(self, msg_subject, msg_body):

        from_addr = 'mg@mit.edu'
        to_addr = ['mgrinich@gmail.com']


        header = 'To: "michael (mit - test)" <mg@mit.com>\n' + \
                 'From: "awesome dude michaelxxxxx" <mgrinich@gmail.com>\n' + 'Subject:' + msg_subject + '\n'
        msg = header + '\n' + msg_body + '\n\n'
        self.conn.sendmail(from_addr, to_addr, msg)




