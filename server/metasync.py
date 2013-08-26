from __future__ import division
import sys, os;  sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..')))

import logging as log
import sys
import sessionmanager
import encoding

# Make logging prettified
from tornado.options import define, options
define("USER_EMAIL", default=None, help="email address to sync", type=str)

from models import db_session, FolderMeta, MessagePart, MessageMeta

from server.util import chunk, human_readable_filesize


crispin_client = None

def bootstrap_user():
    """ Downloads entire messages and
    (1) creates the metadata database
    (2) stores message parts to the block store
    """
    assert options.USER_EMAIL, "Need email address to sync"


    global crispin_client
    crispin_client = sessionmanager.get_crispin_from_email(options.USER_EMAIL)

    log.info('Syncing metadata')

    server_uids = [unicode(s) for s in
            crispin_client.imap_server.search(['NOT DELETED'])]
    log.info("Found {0} UIDs".format(len(server_uids)))


    query = db_session.query(FolderMeta.msg_uid)
    uid_generator = query.filter(FolderMeta.g_email == options.USER_EMAIL)\
                         .filter(FolderMeta.folder_name == crispin_client.all_mail_folder_name() )

    existing_uids = [uid for uid, in uid_generator]

    log.info("Already have {0} items".format(len(existing_uids)))

    warn_uids = set(existing_uids).difference(set(server_uids))
    unknown_uids = set(server_uids).difference(set(existing_uids))

    for uid in warn_uids:
        log.error("Msg {0} doesn't exist on server".format(uid))

    log.info("{0} uids left to fetch".format(len(unknown_uids)))

    total_messages = len(existing_uids)
    unknown_uids = list(unknown_uids)
    unknown_uids.sort(key=int, reverse=True)  # sort as integers, not strings
    log.info("Sorted.")

    rows = db_session.query(FolderMeta.g_msgid).filter(FolderMeta.folder_name == crispin_client.all_mail_folder_name())
    all_g_msgids = [s[0] for s in rows] # chunk_fetch(rows, 200)

    assert len(all_g_msgids) == len(existing_uids), 'Should have the same number of messages as UIDs'

    from sqlalchemy import func

    all_message_size_sum = 0
    for g_msgids in chunk(all_g_msgids, 200):
        all_msgs_query = db_session.query(func.sum(MessageMeta.size)).filter(MessageMeta.g_msgid.in_(g_msgids))
        all_message_size_sum += all_msgs_query.scalar()


    st = [('bytes',0),('KB',0),('MB',1),('GB',6),('TB',2), ('PB',2)]
    log.info("Total blockstore: %s" % human_readable_filesize(all_message_size_sum, suffixes=st))

    resp = crispin_client.imap_server._imap.getquota('')

    from imapclient.response_parser import parse_response

    # (u'OK', '"" (STORAGE 15532925 63997698)')
    assert resp[0] == 'OK'
    # (u'', (u'STORAGE', 15532929, 63997698))
    cmd_name, g_used_size, g_available_size = parse_response(resp[1])[1]

    # units of 1024 octets
    g_used_size *= 1024
    g_available_size *= 1024

    log.info('{0} used of {1}'.format(human_readable_filesize(g_used_size, suffixes=st),
                                      human_readable_filesize(g_available_size, suffixes=st)))


    # cursor = self.db.query(func.sum(Drive.wipe_end - Drive.wipe_start)).filter(Drive.package_id==package.package_id).filter(Drive.wipe_end!=None)
    # total = cursor.scalar()


    class SkipUIDException(Exception): pass
    chunk_size = 15
    log.info("Starting metadata sync with chuncks of size %i" % chunk_size)
    print '\n\n'
    for uids in chunk(unknown_uids, chunk_size):
        # log.info("Fetching from {0} to {1}".format(uids[0], uids[-1]))


        # Crude retry logic
        def fetch_uids_withretry(uids):
            while True:
                try:
                    crispin_client = sessionmanager.get_crispin_from_email(options.USER_EMAIL)
                    return crispin_client.fetch_uids(uids)
                except encoding.EncodingError, e:
                    log.error("Skipping UID %s due to EncodingError: %s" % ( str(uids) , e) )
                    raise SkipUIDException()

                except Exception, e:
                    print e
                    log.exception("Crispin fetch failure: %s. Reconnecting..." % e)
                    pass

        try:
            new_messagemeta, new_messagepart, new_foldermeta = fetch_uids_withretry(uids)
        except SkipUIDException:
            continue

        db_session.add_all(new_foldermeta)
        db_session.add_all(new_messagemeta)
        db_session.add_all(new_messagepart)
        db_session.commit()

        for m in new_messagemeta:
            all_message_size_sum += m.size

        total_messages += len(uids)


        sys.stdout.write("\33[1A\33[2K    Synced {0} of {1} ({2:.4%} done -- {3} of {4})              \n"\
                .format(total_messages,
                        len(server_uids),
                        all_message_size_sum / g_used_size,
                        human_readable_filesize(all_message_size_sum, suffixes=st),
                        human_readable_filesize(g_used_size, suffixes=st)))
        sys.stdout.flush()

        # loading bar
        # pct = total_messages / len(server_uids) * 100
        # sys.stdout.write("\r|%-73s| %.4f%%" % ('#' * int(pct*.73), pct) ),
        # # sys.stdout.write("|%-73s| %.4f%%" % ('#' * int(pct*.73), pct) + '\n')
        # sys.stdout.flush()

    print
    log.info("Finished.")
    return 0



def main():
    options.parse_command_line()
    bootstrap_user()

if __name__ == '__main__':
    sys.exit(main())
