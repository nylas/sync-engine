# allow imports from the top-level dir (we will want to make the package
# system better later)

from imapclient import IMAPClient

import sys
sys.path.insert(0, "..")

import datetime
import logging as log
import tornado

import encoding
from models import IBMessage, IBThread, IBMessagePart


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
                    ssl=True)
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
        log.info("Closing connection.")
        if (self.imap_server):
            self.imap_server.logout()


    @connected
    def select_folder(self, folder):
        try:
            select_info = self.imap_server.select_folder(folder, readonly=True)
        except Exception, e:
            raise e
        log.info('Selected folder %s with %d messages.' % (folder, select_info['EXISTS']) )
        return select_info


    @connected
    def msgids_for_thrids(self, thread_ids):
        self.select_allmail_folder()
        # The boolean IMAP queries use reverse polish notation for
        # the query parameters. imaplib automatically adds parenthesis
        criteria = 'X-GM-THRID %i' % thread_ids[0]
        if len(thread_ids) > 1:
            for t in thread_ids[1:]:
                criteria = 'OR ' + criteria + ' X-GM-THRID %i' % t
        return self.imap_server.search(criteria)



    @connected
    def fetch_messages(self, folder_name):
        select_info = self.select_folder(folder_name)
        log.info(select_info)

        # TODO check and save UID validity
        UIDs = self.imap_server.search(['NOT DELETED'])
        UIDs = [str(s) for s in UIDs]

        new_messages = []

        query = 'ENVELOPE BODY INTERNALDATE'

        log.info("Fetching message headers. Query: %s" % query)
        messages = self.imap_server.fetch(UIDs, [query, 'X-GM-THRID', 'X-GM-MSGID', 'X-GM-LABELS'])
        log.info("Found %i messages." % len(messages.values()))


        for message_uid, message_dict in messages.iteritems():
            new_msg = IBMessage()

            msg_envelope = message_dict['ENVELOPE'] # ENVELOPE is parsed RFC-2822 headers

            def make_unicode_contacts(contact_list):
                n = []
                for c in contact_list:
                    new_c = [None]*len(c)
                    for i in range(len(c)):
                        new_c[i] = encoding.make_unicode(c[i])
                    n.append(new_c)
                return n

            # msg_envelope[0] # we use INTERNALDATE instead of this

            print msg_envelope

            subject = encoding.make_unicode(msg_envelope[1])
            # Headers will wrap when longer than 78 lines per RFC822_2
            subject = subject.replace('\n\t', '').replace('\r\n', '')
            new_msg.subject = subject

            new_msg.from_contacts = make_unicode_contacts(msg_envelope[2])

            all_recipients = []

            sender = msg_envelope[3]
            reply_to = msg_envelope[4]

            if msg_envelope[5]: all_recipients += msg_envelope[5]  # TO
            if msg_envelope[6]: all_recipients += msg_envelope[6]  # CC
            if msg_envelope[7]: all_recipients += msg_envelope[7]  # BCC

            # Not storing yet. Useful for rebuilding threads
            in_reply_to = msg_envelope[8]
            message_id = msg_envelope[9]


            new_msg.to_contacts = make_unicode_contacts(all_recipients)

            new_msg.date = message_dict['INTERNALDATE']  # TOFIX for PST only?
            new_msg.thread_id = message_dict['X-GM-THRID']
            new_msg.message_id = message_dict['X-GM-MSGID']
            new_msg.labels = message_dict['X-GM-LABELS']
            new_msg.uid = str(message_uid)  # specific to folder

            bodystructure = message_dict['BODY']

            # Parse Bodystructure
            all_messageparts = []
            all_attachmentparts = []
            all_signatures = []

            if not bodystructure.is_multipart:
                part = create_messagepart(bodystructure)
                all_messageparts.append(part)

            else:
                # Recursively walk mime objects
                def make_obj(p, i):
                    if not isinstance(p[0], basestring):
                        if isinstance(p[-1], basestring):  # mime relation
                            mime_relation = p[-1]
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

                        for x, part in enumerate(toIterate):
                            if len(i) > 0:
                                index = i+'.' + str(x+1)
                            else:
                                index = str(x+1)

                            ret = make_obj(part, index)  # call recursively and add to lists
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
                                # TODO need to handle RELATED type ...
                                # RELATED
                                log.info("Not sure what to do with mime relation %s" % mime_relation.lower())
                        return []
                    else:
                        if len(i) > 0: index = i+'.1'
                        else: index = '1'
                        return create_messagepart(p, i)


                ret = make_obj(bodystructure, '')
                if len(ret) > 0 and len(all_messageparts) == 0:
                    all_messageparts = ret

            new_msg.message_parts = all_messageparts
            new_msg.attachments = all_attachmentparts
            new_msg.signatures = all_signatures

            print all_messageparts

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


def create_messagepart(p, index='1'):
    assert len(p) > 0

    part = IBMessagePart()
    part.index = str(index)

    if len(p) == 1:
        part.content_type_major = 'multipart'
        part.content_type_minor = p[0]
        return part

    if len(p) == 2:
        part.content_type_major = p[0]
        part.content_type_minor = p[1]
        return part


    # Everything else

    part.content_type_major = p[0]
    part.content_type_minor = p[1]

    if part.content_type_major.lower() == 'text':
        assert len(p) == 8  # TOFIX ?
        if p[2]:  # charset
            try:
                assert p[2][0].lower() == 'charset'
                part.charset = p[2][1]
            except Exception, e:
                log.error('What is here instead? %s' % p[2])
                raise e
        part.encoding = p[5]
        part.bytes = p[6]
        part.line_count = p[7]


    elif part.content_type_major.lower() == 'image':
        assert p[2][0].lower() == 'name'
        assert len(p) == 7  # TOFIX ?
        part.filename = p[2][1]  # Content-Disposition
        part.encoding = p[5]  # Content-Transfer-Encoding
        part.bytes = p[6]

    # Regular file
    else:
        if p[2] and not isinstance(p[2], basestring):  # is there a filename?
            assert p[2][0].lower() == 'name'
            part.filename = p[2][1]
        part.encoding = p[5]
        part.bytes = p[6]

    return part





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





