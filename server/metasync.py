import sys, os;  sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..')))

from inbox import start_mongo; start_mongo()



import crispin
import uuid

import pymongo
import logging as log
import datetime
import google_oauth
from bson.objectid import ObjectId
import sessionmanager
import encoding

# Make logging prettified
import tornado.options
tornado.options.parse_command_line()




db = pymongo.MongoClient().test
try:
    db.create_collection('messages')  # message UID -> main envelope metadata for user.
    db.create_collection('messageparts')  # uid, section for messages.

    db.messages.create_index("uid", unique=True, drop_dups=True )
    log.info('Created collections"')

except pymongo.errors.CollectionInvalid, e:
    if db.create_collection and db.create_collection:
        log.info("DB exists already.")
    else:
        log.error("Error creating sessions DB collecitons. %s" % e)



crispin_client = sessionmanager.get_crispin_from_email('mgrinich@gmail.com')
log.info('fetching threads...')

folder_name = "Inbox"




uids_cursor = db.messages.find( {}, { 'uid': 1} )
existing_uids = [d['uid'] for d in uids_cursor]


new_messages, new_parts = crispin_client.fetch_folder(folder_name)
log.info("Fetched metadata for %i messages and %i parts" % ( len(new_messages), len(new_parts) ) )


filtered_new = [m for m in new_messages if m['uid'] not in existing_uids]
new_uids = [m['uid'] for m in new_messages]
uids_to_remove = [u for u in existing_uids if u not in new_uids]


if len(filtered_new) > 0:
    inserted_ids = db.messages.insert(filtered_new)
    print 'Added %i items.' % len(inserted_ids)

if len(uids_to_remove) > 0:
    db.messages.remove({"uid": {'$in': uids_to_remove}})
    print 'Removed %i items.' % len(uids_to_remove)




## THREADS
log.info("Loading threads for existing message UIDs")
thread_ids_cursor = db.messages.find( {}, { 'x-gm-thrid': 1} )
existing_thread_ids = [d['x-gm-thrid'] for d in thread_ids_cursor]


thread_ids = list(set(existing_thread_ids))

# Below is where we expand the threads and fetch the rest of them
all_msg_uids = crispin_client.msgids_for_thrids(thread_ids)

print 'Message IDs:', all_msg_uids


log.info("Loading stored UIDs")
uids_cursor = db.messages.find( {}, { 'uid': 1} )
existing_uids = [d['uid'] for d in uids_cursor]


unknown_udis =  [str(u) for u in all_msg_uids if str(u) not in existing_uids]

print 'Unknown:', unknown_udis


log.info("Loading %i new messages..." % len(unknown_udis))
new_messages, new_parts = crispin_client.fetch_uids(unknown_udis)
log.info("Fetched metadata for %i messages and %i parts" % ( len(new_messages), len(new_parts) ) )

print new_messages

if len(new_messages) > 0:
    inserted_ids = db.messages.insert(new_messages)
    print 'Added %i items.' % len(inserted_ids)



# for m in new_parts:
#     # if 'name' in m:
#     #   print m['name']
#     log.info("Fetching %s with %s." % ( m['uid'], m['section']))

#     fetched_data =  crispin_client.fetch_msg_body("Inbox", m['uid'], m['section'])

#     msg_data = encoding.decode_data(fetched_data, m['encoding'])

#     print msg_data




