
from mongomgr import startmongo
import os 
import logging as log
from models import IBMessage, IBMessagePart


import pymongo



PATH_TO_MONGO_DATABSE = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "db/mongo/")

startmongo(PATH_TO_MONGO_DATABSE)

from sessionmanager import SessionManager

SessionManager.setup()


### 


folder_name = 'Inbox'

print 'getting cripsin'
crispin_client = SessionManager.get_crispin()

print 'selecting inbox'

select_info = crispin_client.select_folder(folder_name)

UIDs = crispin_client.fetch_all_udids()

print UIDs

UIDs = [str(s) for s in UIDs]

new_messages = []


query = 'ENVELOPE BODY INTERNALDATE'


log.info("Fetching message headers. Query: %s" % query)
messages = crispin_client.imap_server.fetch(UIDs, [query, 'X-GM-THRID', 'X-GM-MSGID', 'X-GM-LABELS'])
log.info("Found %i messages." % len(messages.values()))


for message_uid, message_dict in messages.iteritems():

    new_msg = IBMessage()

    msg_envelope = message_dict['ENVELOPE']

    def clean_header(to_decode):
        from email.header import decode_header
        decoded = decode_header(to_decode)
        parts = [w.decode(e or 'ascii') for w,e in decoded]
        u = u' '.join(parts)
        return u

    new_msg.envelope = msg_envelope

    new_msg.subject = clean_header(msg_envelope[1])
    new_msg.from_contacts = msg_envelope[2]

    # TO, CC, BCC
    all_recipients = []
    if msg_envelope[5]: all_recipients += msg_envelope[5]  # TO
    if msg_envelope[6]: all_recipients += msg_envelope[6]  # CC
    if msg_envelope[7]: all_recipients += msg_envelope[7]  # BCC
    new_msg.to_contacts = all_recipients


    # Return-Path is somewhere between 2-4: ??? <z.daniel.shi@gmail.com>

    # In-Reply-To: = msg_envelope[8]
    # Message-ID = msg_envelope[9]

    new_msg.date = message_dict['INTERNALDATE']
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

                if isinstance(p[-1], basestring):  # p[-1] is the mime relationship                    
                    mime_relation = p[-1]

                    # The objects before the mime relationship label can either be
                    # in the main tuple, or contained in a sub-list
                    if (len(p) == 2):
                        if isinstance(p[0][0], basestring):  # single object
                            toIterate = p[:-1]
                        else:  # Nested list
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


for m in new_messages:
    print m

new_messages

db = pymongo.MongoClient().test
try:
    db.create_collection('messages')
except Exception, e:
    print 'messages db already exists'


result = db.messages.insert([m.toJSON() for m in new_messages])
print 'inserted', result



# return new_messages



