from __future__ import division
import sys, os;  sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..')))

import logging as log
import sys
import sessionmanager

# Make logging prettified
from tornado.options import define, options
define("USER_EMAIL", default=None, help="email address to sync", type=str)

from models import db_session, FolderMeta

from server.util import chunk

def bootstrap_user():
    """ Downloads entire messages and
    (1) creates the metadata database
    (2) stores message parts to the block store
    """
    assert options.USER_EMAIL, "Need email address to sync"

    def refresh_crispin():
        return sessionmanager.get_crispin_from_email(
            options.USER_EMAIL)

    crispin_client = refresh_crispin()

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

    i = 0
    chunk_size = 500
    log.info("Starting metadata sync with chuncks of size %i" % chunk_size)
    for uids in chunk(unknown_uids, chunk_size):
        # log.info("Fetching from {0} to {1}".format(uids[0], uids[-1]))

        try:
            new_messagemeta, new_messagepart, new_foldermeta = crispin_client.fetch_uids(uids)
        except Exception, e:
            log.error("Crispin fetch failusre: %s. Reconnecting..." % e)
            crispin_client = refresh_crispin()
            new_messagemeta, new_messagepart, new_foldermeta = crispin_client.fetch_uids(uids)

        db_session.add_all(new_foldermeta)
        db_session.add_all(new_messagemeta)
        db_session.add_all(new_messagepart)
        db_session.commit()

        total_messages += len(uids)


        # percent_done =  "{0:.4%}".format(total_messages / len(server_uids) )
        # print percent_done + " percent complete         \r",

        pct = total_messages / len(server_uids) * 100
        sys.stdout.write("\r|%-73s| %.4f%%" % ('#' * int(pct*.73), pct) ),
        # sys.stdout.write("|%-73s| %.4f%%" % ('#' * int(pct*.73), pct) + '\n')
        sys.stdout.flush()

        # log.info("Fetched metadata for {0} messages and {1} parts. ({2:.4%} done)"
        #         .format(len(new_messagemeta),
        #                 len(new_messagepart),
        #                 (total_messages / len(server_uids)) ))

    print ""
    log.info("Finished.")

    return 0

if __name__ == '__main__':
    options.parse_command_line()
    sys.exit(bootstrap_user())
