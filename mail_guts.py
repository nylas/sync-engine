# import oauth2 as oauth
import email
# import oauth2.clients.smtp as smtplib
# import oauth2.clients.imap as imaplib
# import time
# import re
# import imaplib as imaplib_original

import auth


from email.header import decode_header


from imapclient import IMAPClient


base_gmail_url = 'https://mail.google.com/mail/b/' + auth.ACCOUNT + '/imap/'
HOST = 'imap.gmail.com'
ssl = True



class AwesomeMail():

    def __init__(self):
        self.server = None

    def setup(self):
        self.server = IMAPClient(HOST, use_uid=True, ssl=ssl)
        self.server.oauth_login(base_gmail_url, 
                                auth.OAUTH_TOKEN, 
                                auth.OAUTH_TOKEN_SECRET, 
                                auth.CONSUMER_KEY, 
                                auth.CONSUMER_SECRET)


        select_info = self.server.select_folder('INBOX', readonly=True)
        print '%d messages in INBOX' % select_info['EXISTS']



    def fetch_latest_message(self):

        messages = self.server.search(['NOT DELETED'])

        latest_email_uid = messages[-1]
        response = self.server.fetch(latest_email_uid, ['RFC822', 'X-GM-THRID', 'X-GM-MSGID'])

        return response[latest_email_uid]['RFC822']

    def fetch_latest_5(self):

        messages = self.server.search(['NOT DELETED'])

        last_5 = messages[-5:]
        response = self.server.fetch(last_5, ['RFC822', 'X-GM-THRID', 'X-GM-MSGID'])


        return [ data['RFC822'] for (msgid, data) in response.iteritems() ]



    def fetch_inbox_subjects(self):

        messages = self.server.search(['NOT DELETED'])

        # messages.reverse()
        messages = messages[-20:] # Just get last 20

        # response = self.server.fetch(messages ['X-GM-THRID', 'X-GM-MSGID'])
        # response = self. server.fetch(messages, ['BODY.PEEK[HEADER.FIELDS (Subject)]', 
                                #            'BODY.PEEK[HEADER.FIELDS (Message-Id)]', 
                            #                'BODY.PEEK[HEADER.FIELDS (From)]', 
                                #            'ENVELOPE', 
                                #            'RFC822.SIZE', 
                                #            'UID', 
                                #            'FLAGS', 
                                #            'INTERNALDATE',
                                #            'X-GM-THRID',
                                #            'X-GM-MSGID',
                                #            'X-GM-LABELS'])
        
        
        response = self. server.fetch(messages, ['BODY.PEEK[HEADER]',
                                         'X-GM-THRID',
                                         'X-GM-MSGID',
                                         'X-GM-LABELS'])

        raw_headers = [data['BODY[HEADER]'] for (msgid, data) in response.iteritems() ]

        emails = [email.message_from_string(rh) for rh in raw_headers]

        subjects = []
        for e in emails:

            header_text = e['Subject']
            default_encoding="ascii"

            headers = decode_header(header_text)
            header_sections = [unicode(text, charset or default_encoding)
                               for text, charset in headers]
            
            header = u"".join(header_sections)

            # Headers will wrap when longer than 78 lines per RFC822_2
            header = header.replace('\n\t', '')
            header = header.replace('\r\n', '')

            subjects.append(header)

        return subjects


        # msg = email.message_from_string(response_part[1])


                    
        #             for header in [ 'subject', 'to', 'from' ]:
        #                 hdr =  '%-8s: %s' % (header.upper(), msg[header])
        #                 self.write(hdr)
        #                 self.write("<br/><br/>")




        # Remove PEEK for indexing

        # return [ data['BODY[HEADER.FIELDS (SUBJECT)]'] for (msgid, data) in response.iteritems() ]




        



#################################################################################

# messages = server.search(['NOT DELETED'])

# print "%d messages that aren't deleted" % len(messages)
# print "Messages:", messages


# response = server.fetch(messages, ['FLAGS', 'RFC822.SIZE'])
# for msgid, data in response.iteritems():
#     print '   ID %d: %d bytes, flags=%s' % (msgid,
#                                             data['RFC822.SIZE'],
#                                             data['FLAGS'])


#################################################################################


# messages = server.search(['NOT DELETED'])

# print "%d messages that aren't deleted" % len(messages)
# print "Messages:", messages


# response = server.fetch(messages, ['INTERNALDATE', 'RFC822', 'X-GM-THRID', 'X-GM-MSGID'])
# for msgid, data in response.iteritems():
#   print '   GM-MSGID: %d, GM-THID: %d' % (data['X-GM-THRID'], data['X-GM-MSGID'])


#################################################################################

# messages = server.search(['NOT DELETED'])

# print "%d messages that aren't deleted" % len(messages)
# print "Messages:", messages


# for message_id in messages:
#   response = server.fetch(message_id, ['INTERNALDATE', 'RFC822', 'X-GM-THRID', 'X-GM-MSGID'])
#   data = response[message_id]

#   print '   GM-MSGID: %d, GM-THID: %d' % (data['X-GM-THRID'], data['X-GM-MSGID'])
#   print '      threads: ', server.search('X-GM-THRID ' + str(data['X-GM-THRID']) )


#################################################################################

# > C0000A UID FETCH 1:* (BODY.PEEK[HEADER.FIELDS (Subject)] BODY.PEEK[HEADER.FIELDS (Message-Id)] ENVELOPE RFC822.SIZE UID FLAGS INTERNALDATE) 
# '(BODY[HEADER.FIELDS (SUBJECT FROM)])'


# mail.uid('search', None, '(HEADER Subject "My Search Term")')
# mail.uid('search', None, '(HEADER Received "localhost")')



# messages = server.search(['NOT DELETED'])
# print "%d messages that aren't deleted" % len(messages)
# print "Messages:", messages

# for message_id in messages:

#   response = server.fetch(message_id, ['BODY.PEEK[HEADER.FIELDS (Subject)]', 
#                                        'BODY.PEEK[HEADER.FIELDS (Message-Id)]', 
#                                        'BODY.PEEK[HEADER.FIELDS (From)]', 
#                                        'ENVELOPE', 
#                                        'RFC822.SIZE', 
#                                        'UID', 
#                                        'FLAGS', 
#                                        'INTERNALDATE',
#                                        'X-GM-THRID',
#                                        'X-GM-MSGID',
#                                        'X-GM-LABELS'])

#   data = response[message_id]

#   e = data['ENVELOPE']
#   date = e[0]
#   subject = e[1]

    # ('Tue, 11 Oct 2011 12:45:48 -0400', 'Re: Domain: www.marvelo.us', 
    # (('All So', None, 'allsolut', 'gmail.com'),), 
    # ((None, None, 'marshallreeves', 'gmail.com'),), 
    # (('All So', None, 'allsolut', 'gmail.com'),), 
    # (('Michael Grinich', None, 'mgrinich', 'gmail.com'),)
    # , None, 
    # None, 
    # '<CAO3aFYs2gCLBOpptd2wwAf39F1QTYOYKpthW6Sk6zF3FMbf3=g@mail.gmail.com>', 
    # '<CAOD34DkssR5892ASMv=8FkxqegJVLXXTULc3LnMgPETP6+DPcg@mail.gmail.com>') 


    # print '    %s  (%s)' % ( subject, date)
    
    # print '   GM-MSGID: %d, GM-THID: %d' % (data['X-GM-THRID'], data['X-GM-MSGID'])




# for message_id in messages:
#   response = server.fetch(message_id, ['INTERNALDATE', 'RFC822', 'X-GM-THRID', 'X-GM-MSGID'])
#   data = response[message_id]
    
    # message = data['RFC822']




# Gmail IMAP    extensions
#   X-GM-LABELS
#   X-GM-MSGID
#   X-GM-THRID
#   X-GM-RAW
#   XLIST



# >>> 