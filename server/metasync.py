import sys, os;  sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..')))


import crispin
import uuid

import logging as log
import sessionmanager

import encoding

# Make logging prettified
import tornado.options
tornado.options.parse_command_line()

# from lamson import encoding

from sqlalchemy import *
from models import db_session, Base, MessageMeta, MessagePart
from sqlalchemy.orm import defer

def sync_meta():

    crispin_client = sessionmanager.get_crispin_from_email('mgrinich@gmail.com')

    folder_name = crispin_client.all_mail_folder_name()
    # folder_name = 'Inbox'

    log.info('Syncing metadata for %s' % folder_name)
    select_info = crispin_client.select_folder(folder_name)

    UIDs = crispin_client.imap_server.search(['NOT DELETED'])
    UIDs = [str(s) for s in UIDs]
    log.info("Found %i UIDs" % len(UIDs) )

    query = db_session.query(MessageMeta).options(
                    defer(MessageMeta._from_addr),
                    defer(MessageMeta._sender_addr),
                    defer(MessageMeta._reply_to),
                    defer(MessageMeta._to_addr),
                    defer(MessageMeta._cc_addr),
                    defer(MessageMeta._bcc_addr),
                    defer(MessageMeta._in_reply_to),
                    defer(MessageMeta.g_labels),
                    defer(MessageMeta.subject),
                    )

    existing_msgs = query.all()
    existing_uids = [m.uid for m in existing_msgs]

    log.info("Already have %i items" % len(existing_uids))
    uids_dict = {}
    for u in UIDs:
        uids_dict[u] = True

    for u in existing_uids:
        try:
            del uids_dict[u]
        except Exception, e:
            log.error('UID not in dict: %s' % u)
            continue
    unknown_UIDs = uids_dict.keys()

    log.info("%i uids left to fetch" % len(unknown_UIDs))


    count = 0

    batch_fetch_amount = 1000

    for i in reversed((xrange(0, len(unknown_UIDs), batch_fetch_amount))):

        start, end = i, min(len(unknown_UIDs), i+batch_fetch_amount)
        log.info("Fetching from %s to %s" % (start, end) )

        to_fetch = unknown_UIDs[start:end]

        new_messages, new_parts = crispin_client.fetch_uids(to_fetch)


        db_session.add_all(new_messages)
        db_session.commit()

        db_session.add_all(new_parts)
        db_session.commit()

        count += len(new_messages)

        log.info("Fetched metadata for %i messages and %i parts. (total: %i)" % ( len(new_messages), len(new_parts), count ) )

    log.info("Finished.")




def sync_parts():

    crispin_client = sessionmanager.get_crispin_from_email('mgrinich@gmail.com')
    # folder_name = crispin_client.all_mail_folder_name()
    # select_info = crispin_client.select_folder(folder_name)

    log.info("Loading parts from DB")
    parts = db_session.query(MessagePart).all()
    log.info("We have %i parts to downlod" % len(parts))

    for part in parts:
        print 'part:', part.encoding, part.charset

        messages_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "../messageparts/")
        write_dir = os.path.join(messages_path,
                                  part.g_msgid[0],
                                  part.g_msgid[1],
                                  part.g_msgid[2],
                                  part.g_msgid[3])
        if not os.path.exists(write_dir):
            os.makedirs(write_dir)

        write_path = os.path.join(write_dir, part.g_msgid + '-' + part.section)

        if os.path.exists(write_path):
            log.info("Already have file %s" % write_path)
            continue


        log.info("Fetching...")
        msg_data = crispin_client.fetch_msg_body(part.allmail_uid, part.section)

        if not msg_data:
            log.error("Message has no body %s" % part)
            continue


        try:
            msg_data = encoding.decode_part(msg_data, part)
        except UnicodeDecodeError, e:
            print 'msg_data', msg_data
            raise e


        log.info("Writing to %s" % write_path)

        if isinstance(msg_data, unicode):
            msg_data = msg_data.encode("utf-8")
        f = open(write_path, 'w')
        f.write(msg_data)
        f.close()


    log.info("Finished.")




    # import codecs
    # from email.header import decode_header

    # import email

    # # from email.parser import parser

    # # parser = Parser()

    # batch_fetch_amount = 500
    # for i in reversed((xrange(0, len(UIDs) -1, batch_fetch_amount))):
    #     start, end = i, min(len(UIDs) -1, i+batch_fetch_amount)
    #     log.info("Fetching from UIDs %s to %s" % (UIDs[start], UIDs[end]) )
    #     to_fetch = UIDs[start:end]

    #     headers = crispin_client.fetch_entire_msg(to_fetch)


    #     for fetched in to_fetch:
    #         body = headers[int(fetched)]['BODY[]']

    #         try:

    #             # default_encoding="ascii"
    #             # txt = body
    #             # try:
    #             #     body = u"".join([unicode(text, charset or default_encoding, 'strict')
    #             #             for text, charset in decode_header(txt)])
    #             # except Exception, e:
    #             #     log.error("Problem converting string to unicode: %s" % txt)
    #             #     body = u"".join([unicode(text, charset or default_encoding, 'replace')
    #             #             for text, charset in decode_header(txt)])

    #             # # body = unicode(body.strip(codecs.BOM_UTF8), 'utf-8')

    #             # mailbase = encoding.from_string(body)

    #             email_obj = email.message_from_string(body, strict='replace')
    #             # print email_obj
    #             # print 'parsed %i msgs' % len(email_obj)

    #         except Exception, e:
    #             print e
    #             continue

    #     # print headers
    #     print

    # return



    # new_messages, new_parts = crispin_client.fetch_folder(folder_name)


    # filtered_new = [m for m in new_messages if m['uid'] not in existing_uids]
    # new_uids = [m['uid'] for m in new_messages]
    # uids_to_remove = [u for u in existing_uids if u not in new_uids]


    # if len(filtered_new) > 0:
    #     inserted_ids = db.messages.insert(filtered_new)
    #     print 'Added %i items.' % len(inserted_ids)

    # if len(uids_to_remove) > 0:
    #     db.messages.remove({"uid": {'$in': uids_to_remove}})
    #     print 'Removed %i items.' % len(uids_to_remove)


    # ## THREADS
    # log.info("Loading threads for existing message UIDs")
    # thread_ids_cursor = db.messages.find( {}, { 'x-gm-thrid': 1} )
    # existing_thread_ids = [d['x-gm-thrid'] for d in thread_ids_cursor]


    # thread_ids = list(set(existing_thread_ids))

    # # Below is where we expand the threads and fetch the rest of them
    # all_msg_uids = crispin_client.msgids_for_thrids(thread_ids)

    # print 'Message IDs:', all_msg_uids


    # log.info("Loading stored UIDs")
    # uids_cursor = db.messages.find( {}, { 'uid': 1} )
    # existing_uids = [d['uid'] for d in uids_cursor]


    # unknown_udis =  [str(u) for u in all_msg_uids if str(u) not in existing_uids]

    # print 'Unknown:', unknown_udis


    # log.info("Loading %i new messages..." % len(unknown_udis))


    # new_messages, new_parts = crispin_client.fetch_uids(unknown_udis)
    # log.info("Fetched metadata for %i messages and %i parts" % ( len(new_messages), len(new_parts) ) )

    # print new_messages

    # if len(new_messages) > 0:
    #     inserted_ids = db.messages.insert(new_messages)
    #     print 'Added %i items.' % len(inserted_ids)



    # for m in new_parts:
    #     # if 'name' in m:
    #     #   print m['name']
    #     log.info("Fetching %s with %s." % ( m['uid'], m['section']))

    #     fetched_data =  crispin_client.fetch_msg_body("Inbox", m['uid'], m['section'])

    #     msg_data = encoding.decode_data(fetched_data, m['encoding'])

    #     print msg_data

if __name__ == '__main__':
    # sync_meta()
    sync_parts()
