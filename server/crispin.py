# allow imports from the top-level dir (we will want to make the package
# system better later)

from imapclient import IMAPClient

import sys
sys.path.insert(0, "..")

from email.Parser import Parser
from email import message_from_string
from email.Iterators import typed_subpart_iterator
import datetime
import logging as log
import tornado

import auth
import encoding

from models import IBMessage, IBThread, IBMessagePart


USE_SSL = True

# BASE_GMAIL_IMAP_URL = 'https://mail.google.com/mail/b/' + ACCOUNT + '/imap/'
# BASE_GMAIL_SMTP_UTL = 'https://mail.google.com/mail/b/' + ACCOUNT + '/smtp/'

IMAP_HOST = 'imap.gmail.com'
SMTP_HOST = 'smtp.gmail.com'





class AuthFailure(Exception): pass
class TooManyConnectionsFailure(Exception): pass



class CrispinClient:
    # 20 minutes
    SERVER_TIMEOUT = datetime.timedelta(seconds=1200)

    def __init__(self, email_address, oauth_token):

        self.email_address = email_address
        self.oauth_token = oauth_token
        self.imap_server = None
        # last time the server checked in, in UTC
        self.keepalive = None


    def server_needs_refresh(self):
        """ Many IMAP servers have a default minimum "no activity" timeout
            of 30 minutes. Sending NOPs ALL the time is hells slow, but we
            need to do it at least every 30 minutes.
        """
        now = datetime.datetime.utcnow()
        return self.keepalive is None or \
                (now - self.keepalive) > self.SERVER_TIMEOUT


    def connected(fn):
        """ A decorator for methods that can only be run on a logged-in client.
        """
        def connected_fn(self, *args, **kwargs):
            if self.server_needs_refresh():
                self._connect()
            ret = fn(self, *args, **kwargs)
            # a connected function did *something* with our connection, so
            # update the keepalive
            self.keepalive = datetime.datetime.utcnow()
            return ret
        return connected_fn


    def _connect(self):
        log.info('Connecting to %s ...' % IMAP_HOST,)

        try:
            self.imap_server.noop()
            if self.imap_server.state == 'NONAUTH' or self.imap_server.state == 'LOGOUT':
                raise Exception
            log.info('Already connected to host.')
            return True
        # XXX eventually we want to do stricter exception-checking here
        except Exception, e:
            log.info('No active connection. Opening connection...')

        try:
            self.imap_server = IMAPClient(IMAP_HOST, use_uid=True,
                    ssl=USE_SSL)
            # self.imap_server.debug = 4  # todo
            log.info("Logging in: %s" % self.email_address)
            self.imap_server.oauth2_login(self.email_address, self.oauth_token)

        except Exception as e:
            if str(e) == '[ALERT] Too many simultaneous connections. (Failure)':
                raise TooManyConnectionsFailure("Too many simultaneous connections.")
            elif str(e) == '[ALERT] Invalid credentials (Failure)':
                raise AuthFailure("Invalid credentials")
            else:
                raise e
                log.error(e)

            self.imap_server = None
            return False


        log.info('Connection successful.')
        return True


    def stop(self):
        log.info("Stopping crispin")
        if (self.imap_server):
            loop = tornado.ioloop.IOLoop.instance()
            # For autoreload
            try:
                loop.add_callback(self.imap_server.logout)
            except Exception, e:
                self.imap_server.logout()


    @connected
    def list_folders(self):
        try:
            resp = self.imap_server.xlist_folders()
        except Exception, e:
            raise e
        return [dict(flags = f[0], delimiter = f[1], name = f[2]) for f in resp]

    def all_mail_folder_name(self):
        folders = self.list_folders()
        for f in folders:
            if u'\\AllMail' in f['flags']:
                return f['name']


    @connected
    def select_folder(self, folder):
        try:
            select_info = self.imap_server.select_folder(folder, readonly=True)
        except Exception, e:
            log.error("<select_folder> %s" % e)
            raise e

        # TODO make sure UIDVALIDITY is the same value here.
        # If it's not, we can no longer use old UIDs.
        log.info('Selected folder %s with %d messages.' % (folder, select_info['EXISTS']) )
        return select_info


    @connected
    def fetch_all_udids(self):
        UIDs = self.imap_server.search(['NOT DELETED'])
        return UIDs


    @connected
    def fetch_thread(self, thread_id):
        threads_msg_ids = self.imap_server.search('X-GM-THRID %s' % str(thread_id))
        return threads_msg_ids


    @connected
    def fetch_messages_for_thread(self, thread_id):
        """ Returns list of IBMessage objects corresponding to thread_id """
        threads_msg_ids = self.imap_server.search('X-GM-THRID %s' % str(thread_id))
        log.info("Msg ids for thread: %s" % threads_msg_ids)

        folder_name = self.all_mail_folder_name()
        UIDs = threads_msg_ids
        msgs = self.fetch_headers_for_uids(folder_name, UIDs)

        return msgs


    @connected
    def fetch_messages(self, folder_name):

        # Get messages in requested folder
        select_info = self.select_folder(folder_name)
        UIDs = self.fetch_all_udids()

        msgs = self.fetch_headers_for_uids(folder_name, UIDs)

        return msgs



        # TODO Add expand the threads 

        # thread_ids = list(set([m.thread_id for m in msgs]))
        # log.info("For %i messages, found %i threads total." % (len(msgs), len(thread_ids)))


        # # Below is where we expand the threads and fetch the rest of them
        # self.select_allmail_folder() # going to fetch all messages in threads
        # all_msg_uids = self.msgids_for_thrids(thread_ids)

        # log.info("Expanded to %i messages for %i thread IDs." % (len(all_msg_uids), len(thread_ids)))

        # all_msgs = self.fetch_headers_for_uids(self.all_mail_folder_name(), all_msg_uids)

        # return all_msgs

        # threads = {}
        # # Group by thread id
        # for m in all_msgs:
        #     if m.thread_id not in threads.keys():
        #         new_thread = IBThread()
        #         new_thread.thread_id = m.thread_id
        #         threads[m.thread_id] = new_thread
        #     t = threads[m.thread_id]
        #     t.message_ids.append(m.message_id)
        # all_threads = threads.values()

        # log.info("Returning %i threads with total of %i messages." % (len(all_threads), len(all_msgs)))

        # return all_threads



    @connected
    def fetch_headers_for_uids(self, folder_name, UIDs):
        if isinstance(UIDs, int ):
            UIDs = [str(UIDs)]
        elif isinstance(UIDs, basestring):
            UIDs = [UIDs]


        UIDs = [str(s) for s in UIDs]

        new_messages = []

        select_info = self.select_folder(folder_name)

        query = 'ENVELOPE BODY INTERNALDATE'

        log.info("Fetching message headers. Query: %s" % query)
        messages = self.imap_server.fetch(UIDs, [query, 'X-GM-THRID', 'X-GM-MSGID', 'X-GM-LABELS'])
        log.info("Found %i messages." % len(messages.values()))


        for message_uid, message_dict in messages.iteritems():
            
            # unparsed_headers = message_dict[query_key]
            # email_msg_object = message_from_string(unparsed_headers)
            # new_msg = IBMessage(email_msg_object)

            new_msg = IBMessage()


            # ENVELOPE on
            # A parsed representation of the [RFC-2822] header of the message.
            msg_envelope = message_dict['ENVELOPE']

            # ('Tue, 21 May 2013 08:41:20 -0700', 
            #  '[SALT] De-extinction TONIGHT Tues. May 21', 
            #  (('Stewart Brand', None, 'sb', 'longnow.org'),), 
            #  ((None, None, 'salt-bounces', 'list.longnow.org'),), 
            #  ((None, None, 'services', 'longnow.org'),), 
            #  (('SALT list', None, 'salt', 'list.longnow.org'),), 
            #  None, 
            #  None, 
            #  None, 
            #  '<89ACAE66-4C10-4BBF-9B24-AC18A0FB2440@longnow.org>')


            def make_unicode_contacts(contact_list):
                n = []
                for c in contact_list:
                    new_c = [None]*len(c)
                    for i in range(len(c)):
                        new_c[i] = encoding.make_unicode(c[i])
                    n.append(new_c)
                return n

            # msg_envelope[0] # date


            subject = encoding.make_unicode(msg_envelope[1])
            # Headers will wrap when longer than 78 lines per RFC822_2
            subject = subject.replace('\n\t', '').replace('\r\n', '')
            new_msg.subject = subject


            new_msg.from_contacts = make_unicode_contacts(msg_envelope[2])
            # Errors-To: salt-bounces@list.longnow.org
            # Sender: salt-bounces@list.longnow.org

            # Reply-To: services@longnow.org
            # new_msg.reply_to = msg_envelope[4]

            # TO, CC, BCC


            all_recipients = []
            if msg_envelope[5]: all_recipients += msg_envelope[5]  # TO
            if msg_envelope[6]: all_recipients += msg_envelope[6]  # CC
            if msg_envelope[7]: all_recipients += msg_envelope[7]  # BCC
            new_msg.to_contacts = make_unicode_contacts(all_recipients)


            # Return-Path is somewhere between 2-4: ??? <z.daniel.shi@gmail.com>

            # TO: = msg_evelope[5]
            # CC = msg_envelope[6]
            # BCC: = msg_envelope[7]
            # In-Reply-To: = msg_envelope[8]
            # Message-ID = msg_envelope[9]

            

            # This date seems to work since I'm in SF. 
            new_msg.date = message_dict['INTERNALDATE']


            # Here's the previous code from when I was parsing rfc822 headers...
            # Gmail's timezone is usually UTC-07:00
            # http://stackoverflow.com/questions/11218727/what-timezone-does-gmail-use-for-internal-imap-mailstore

            # date_tuple_with_tz = email_utils.parsedate_tz(email_message_object["Date"])
            # utc_timestamp = email_utils.mktime_tz(date_tuple_with_tz)
            # time_epoch = time.mktime( date_tuple_with_tz[:9] )
            # self.date = datetime.datetime.fromtimestamp(utc_timestamp)


            new_msg.thread_id = message_dict['X-GM-THRID']
            new_msg.message_id = message_dict['X-GM-MSGID']
            new_msg.labels = message_dict['X-GM-LABELS']

            # This is stupid because it's specific to the folder where we found it.
            new_msg.uid = str(message_uid)


            # BODYSTRUCTURE parsing 

            all_messageparts = []
            all_attachmentparts = []
            all_signatures = []

            bodystructure = message_dict['BODY']


            if not bodystructure.is_multipart:
                all_messageparts.append(IBMessagePart(bodystructure, '1'))
    
            else:



            # This recursively walks objects returned in bodystructure
                def make_obj(p, i):
                    if not isinstance(p[0], basestring):
                        # if isinstance(p[-1], basestring):
                        #     print 'Relation: %s' % p[-1]
                        # else:
                        #     print 'No relation var?', p[-1]


                        if isinstance(p[-1], basestring):  # p[-1] is the mime relationship
                            
                            mime_relation = p[-1]

                            # The objects before the mime relationship label can either be
                            # in the main tuple, or contained in a sub-list

                            if (len(p) == 2):

                                # single object
                                if isinstance(p[0][0], basestring):
                                    toIterate = p[:-1]
                                # Nested list
                                else:
                                    toIterate = p[0]

                            # probably have multiple objects here
                            else:
                                toIterate = p[:-1]

                        else:
                            # No relationship var here
                            log.error("NO MIME RELATION HERE.....")
                            toIterate = p

                        stragglers = []
                        for x, part in enumerate(toIterate):  
                            if len(i) > 0:
                                index = i+'.' + str(x+1)
                            else:
                                index = str(x+1)

                            ret = make_obj(part, index)
                            if not ret: continue

                            assert isinstance(ret, IBMessagePart)

                            if mime_relation.lower() == 'alternative':
                                all_messageparts.append(ret)
                                
                            elif mime_relation.lower() == 'mixed':
                                if ret.content_type_major.lower() == 'text':
                                    all_messageparts.append(ret)
                                else:
                                    all_attachmentparts.append(ret)

                            elif mime_relation.lower() == 'signed':
                                if ret.content_type_major.lower() == 'text':
                                    all_messageparts.append(ret)
                                else:
                                    all_signatures.append(ret)

                            else:
                                # MIXED
                                # ALTERNATIVE
                                # RELATED
                                # SIGNED
                                log.info("Not sure what to do with mime relation %s" % mime_relation.lower())

                        return []

                    else:
                        if len(i) > 0: index = i+'.1'
                        else: index = '1'
                        return IBMessagePart(p, i)
                

                ret = make_obj(bodystructure, '')
                if len(ret) > 0 and len(all_messageparts) == 0:
                    all_messageparts = ret


            new_msg.message_parts = all_messageparts
            new_msg.attachments = all_attachmentparts
            new_msg.signatures = all_signatures

            new_messages.append(new_msg)

        log.info("Fetched headers for %i messages" % len(new_messages))
        return new_messages



    @connected
    def fetch_msg_body(self, msg_uid, section_index='1', folder=None):
        msg_uid = str(msg_uid)
        if not folder:
            folder = self.all_mail_folder_name()

        self.select_folder(folder)
        log.info("Fetching in %s -- %s <%s>" % (folder, msg_uid, section_index))
        query = 'BODY.PEEK[%s]' % section_index
        query_key = 'BODY[%s]' % section_index
        response = self.imap_server.fetch(msg_uid,
                                    [query, 'X-GM-THRID', 'X-GM-MSGID'])

        try:
            response_dict =  response[int(msg_uid)]
        except KeyError, e:
            print 'Response:', response
            return "Error fetching."
        
        body_data = response_dict[query_key]
        message_id = response_dict['X-GM-MSGID']
        thread_id = response_dict['X-GM-THRID']

        return body_data







