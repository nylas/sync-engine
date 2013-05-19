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

from models import IBMessage, IBThread, IBMessagePart

from datastore import DataStore

from imaplib2 import Internaldate2Time


class CrispinClient:
    # 20 minutes
    SERVER_TIMEOUT = datetime.timedelta(seconds=1200)

    def __init__(self):
        self.imap_server = None
        # last time the server checked in, in UTC
        self.keepalive = None
        self.datastore = DataStore()

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
        log.info('Connecting to %s ...' % auth.IMAP_HOST,)

        try:
            self.imap_server.noop()
            log.info('Already connected to host.')
            return True
        # XXX eventually we want to do stricter exception-checking here
        except Exception, e:
            log.info('No active connection. Opening connection...')

        try:
            self.imap_server = IMAPClient(auth.IMAP_HOST, use_uid=True,
                    ssl=auth.SSL)
            # self.imap_server.debug = 4  # todo
            self.imap_server.oauth_login(auth.BASE_GMAIL_IMAP_URL,
                        auth.OAUTH_TOKEN,
                        auth.OAUTH_TOKEN_SECRET,
                        auth.CONSUMER_KEY,
                        auth.CONSUMER_SECRET)
        except Exception as e:
            if str(e) == '[ALERT] Too many simultaneous connections. (Failure)':
                log.error("Too many open IMAP connection.")
            # raise e
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
    def get_special_folder(self, special_folder):
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



    @connected
    def select_folder(self, folder):
        try:
            select_info = self.imap_server.select_folder(folder, readonly=True)
        except Exception, e:
            log.error("<select_folder> %s" % e)
            # raise e
            return None
            
        # Format of select_info
        # {'EXISTS': 3597, 'PERMANENTFLAGS': (),
        # 'UIDNEXT': 3719,
        # 'FLAGS': ('\\Answered', '\\Flagged', '\\Draft', '\\Deleted', '\\Seen', '$Pending', 'Junk', 'NonJunk', 'NotJunk', '$Junk', 'Forwarded', '$Forwarded', 'JunkRecorded', '$NotJunk'),
        # 'UIDVALIDITY': 196, 'READ-ONLY': [''], 'RECENT': 0}
        log.info('Selected folder %s with %d messages.' % (folder, select_info['EXISTS']) )
        return select_info


    def select_allmail_folder(self):
        return self.select_folder(self.all_mail_folder_name())



    @connected
    def fetch_msg(self, msg_uid):
        msg_uid = long(msg_uid)  # sometimes comes as string

        # m = self.datastore.message(msg_uid)
        # if (m): return m

        log.info("Fetching message. UID: %i" % msg_uid)
        response = self.imap_server.fetch(
                str(msg_uid), ['RFC822', 'X-GM-THRID', 'X-GM-MSGID'])

        if len(response.keys()) == 0:
            log.error("No response for msg query. msg_id = %s", msg_uid)
            return None

        raw_response = response[msg_uid]['RFC822']
        log.info("Received response. Size: %i" % len(raw_response))

        msg = Parser().parsestr(raw_response)

        # headers

        new_msg = IBMessage(msg)


        # Parse the body here
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

        # TODO Run trim_quoted_text here for the message

        if content_type == 'text/plain':
            pass
            # TODO here convert plain text to HTML text somehow...

        # TODO here run fix_links which converts links to HTML I think...
        new_msg.body_text = msg_text


        m = self.datastore.addMessage(new_msg)

        return new_msg

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
        msgs = []
        for msg_id in threads_msg_ids:
            m = self.fetch_msg(msg_id)
            msgs.append(m)
        return msgs


    @connected
    def fetch_threads(self, folder_name):

        # Get messages in requested folder
        select_info = self.select_folder(folder_name)
        UIDs = self.fetch_all_udids()

        msgs = self.fetch_headers_for_uids(folder_name, UIDs)

        threads = {}
        # Group by thread id
        for m in msgs:
            if m.thread_id not in threads.keys():
                new_thread = IBThread()
                new_thread.thread_id = m.thread_id
                threads[m.thread_id] = new_thread
            t = threads[m.thread_id]
            t.message_ids.append(m.message_id)
        threads = threads.values()

        log.info("For %i messages, found %i threads total." % (len(msgs), len(threads)))


        # TODO remove this
        # return threads



        # Below is where we expand the threads and fetch the rest of them
        self.select_allmail_folder() # going to fetch all messages in threads


        thread_ids = [t.thread_id for t in threads]

        # The boolean IMAP queries use reverse polish notation for
        # the query parameters. imaplib automatically adds parenthesis 
        criteria = 'X-GM-THRID %i' % thread_ids[0]
        if len(thread_ids) > 1:
            for t in thread_ids[1:]:
                criteria = 'OR ' + criteria + ' X-GM-THRID %i' % t
        all_msg_uids = self.imap_server.search(criteria)        

        log.info("Expanded to %i messages for %i thread IDs." % (len(all_msg_uids), len(thread_ids)))

        all_msgs = self.fetch_headers_for_uids(self.all_mail_folder_name(), all_msg_uids)


        threads = {}
        # Group by thread id
        for m in msgs:
            if m.thread_id not in threads.keys():
                new_thread = IBThread()
                new_thread.thread_id = m.thread_id
                threads[m.thread_id] = new_thread
            t = threads[m.thread_id]
            t.message_ids.append(m.message_id)
        all_threads = threads.values()

        log.info("Returning %i threads with total of %i messages." % (len(all_threads), len(all_msgs)))

        return all_threads



    @connected
    def fetch_headers_for_uids(self, folder_name, UIDs):
        if isinstance(UIDs, int ):
            UIDs = [str(UIDs)]
        elif isinstance(UIDs, basestring):
            UIDs = [UIDs]

        # TODO: keep track of current folder so we don't select twice

        # print 'Lets do all mail instead'
        # folder_name = self.all_mail_folder_name()
        # print 'Select it'
        # folder_name = 'Awesome'

        select_info = self.select_folder(folder_name)
        # UIDs = self.fetch_all_udids()

    #     to_grab = 200
    #     i = 0

    #     print 'doit now'
    #     fetched_messages = []
    #     while i+to_grab < len(UIDs):
    #         search_this = UIDs[i:i+to_grab]
    #         f = self.fetch_headers_block(search_this)
    #         fetched_messages += f
    #         print 'fetched %s' % len(search_this)
    #         i+= to_grab

    #     return fetched_messages




    # def fetch_headers_block(self, UIDs):

        query = 'ENVELOPE BODY INTERNALDATE'

        log.info("Fetching message headers. Query: %s" % query)
        messages = self.imap_server.fetch(UIDs, [query, 'X-GM-THRID', 'X-GM-MSGID', 'X-GM-LABELS'])
        log.info("Found %i messages." % len(messages.values()))

        new_messages = []
        new_bodystructures = []


        for message_uid, message_dict in messages.iteritems():
            
            # print 'ENVELOPE', message_dict['ENVELOPE']
            # print 'BODY', message_dict['BODY']
            # print

            # unparsed_headers = message_dict[query_key]
            # email_msg_object = message_from_string(unparsed_headers)
            # new_msg = IBMessage(email_msg_object)

            new_msg = IBMessage()

            new_msg.date = message_dict['INTERNALDATE']
            new_msg.thread_id = message_dict['X-GM-THRID']
            new_msg.message_id = message_dict['X-GM-MSGID']
            new_msg.labels = message_dict['X-GM-LABELS']


            bodystructure = message_dict['BODY']


            if bodystructure.is_multipart:

                assert len(bodystructure) <= 2
                # TODO look into the multipart grouping p[-1]. these fall under:
                # MIXED
                # ALTERNATIVE
                # RELATED
                # SIGNED

                parts = bodystructure[0]

                for i, part in enumerate(parts):
                    # Sometimes one of the body parts is actually something
                    # weird like Content-Type: multipart/alternative, so you
                    # have to loop though them individually. I think
                    # email.parser takes care of this when you fetch the actual
                    # body content, but I have to do it here for the
                    # BODYSTRUCTURE response.

                    # recurisve creator since these might be nested
                    # pass the index so we can append subindicies
                    # Note: this shit might break but it works for now...
                    def make_obj(p, i):
                        if not isinstance(p[0], basestring):
                            for x in range(len(p) - 1): # The last one is the label
                                if len(i) > 0: index = i+'.'+ str(x+1)
                                else: index = str(x+1)
                                make_obj(p[x], index)
                        else:
                            if len(i) > 0: index = i+'.1'
                            else: index = '1'
                            new_bodystructures.append(IBMessagePart(p,i))
                    make_obj(part, str(i+1))

            else:
                new_bodystructures.append(IBMessagePart(bodystructure, '1'))







            new_messages.append(new_msg)

        log.info("Fetched headers for %i messages" % len(new_messages))
        
        return new_messages



######################


        query = 'BODY.PEEK[HEADER.FIELDS (TO CC FROM DATE SUBJECT)]'
        query_key = 'BODY[HEADER.FIELDS (TO CC FROM DATE SUBJECT)]'

        log.info("Fetching message headers. Query: %s" % query)
        messages = self.imap_server.fetch(UIDs, [query, 'X-GM-THRID', 'X-GM-MSGID', 'X-GM-LABELS'])
        log.info("Found %i messages." % len(messages.values()))

        new_messages = []

        for message_uid, message_dict in messages.iteritems():
            unparsed_headers = message_dict[query_key]
            email_msg_object = message_from_string(unparsed_headers)

            new_msg = IBMessage(email_msg_object)
            new_msg.thread_id = message_dict['X-GM-THRID']
            new_msg.message_id = message_dict['X-GM-MSGID']
            new_msg.labels = message_dict['X-GM-LABELS']

            new_messages.append(new_msg)

        log.info("Fetched headers for %i messages" % len(new_messages))
        return new_messages




    @connected
    def fetch_IBMessagePart(self, UIDs):
        if isinstance(UIDs, int ):
            UIDs = [str(UIDs)]
        elif isinstance(UIDs, basestring):
            UIDs = [UIDs]

        query = 'ENVELOPE BODY INTERNALDATE'

        # envelope gives relevant headers and is really fast in practice
        # RFC822.HEADER will give *all* of the headers, and is probably slower? // TODO
        # query = 'RFC822.HEADER BODY'
        # query = 'FLAGS UID RFC822.SIZE INTERNALDATE BODY.PEEK[HEADER] BODY'

        log.info("Fetching messages with query: %s" % query )
        messages = self.imap_server.fetch(UIDs, [query, 'X-GM-THRID'])
        log.info("  ...found %i messages." % len(messages.values()))

        bodystructure_parts = []

        for msgid, data in messages.iteritems():
            bodystructure = data['BODY']

            if bodystructure.is_multipart:
                # XXX only look at the first part for now
                parts = bodystructure[0]

                for i, part in enumerate(parts):
                    # Sometimes one of the body parts is actually something
                    # weird like Content-Type: multipart/alternative, so you
                    # have to loop though them individually. I think
                    # email.parser takes care of this when you fetch the actual
                    # body content, but I have to do it here for the
                    # BODYSTRUCTURE response.

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
                            bodystructure_parts.append(IBMessagePart(p,i))
                    make_obj(part, str(i+1))

            else:
                bodystructure_parts.append(IBMessagePart(bodystructure, '1'))

        return bodystructure_parts

