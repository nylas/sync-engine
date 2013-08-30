#!/usr/bin/env python
from __future__ import division
import sys, os;  sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..')))

import sys
import sessionmanager

import argparse

from models import db_session, FolderMeta, UIDValidity

from sqlalchemy import distinct
import sqlalchemy.exc

from encoding import EncodingError

from server.util import chunk, partition

from util.log import configure_logging
log = configure_logging()

def refresh_crispin(email):
    return sessionmanager.get_crispin_from_email(email)

def load_validity_cache(crispin_client, email, SYNC_FOLDERS):
    # in practice UIDVALIDITY and HIGHESTMODSEQ are always positive
    # integers with gmail, but let's not take chances on our default.
    defaults = dict(UIDVALIDITY=float('-inf'), HIGHESTMODSEQ=float('-inf'))
    # populated cache looks like:
    # {'Inbox': {'UIDVALIDITY': 123, 'HIGHESTMODSEQ': 456}}
    cache_validity = dict([(folder, defaults.copy()) for folder in SYNC_FOLDERS])
    for folder, uid_validity, highestmodseq in db_session.query(
            UIDValidity.folder_name,
            UIDValidity.uid_validity,
            UIDValidity.highestmodseq).filter_by(
                    g_email=email, folder_name=folder):
        cache_validity[folder] = dict(UIDVALIDITY=uid_validity,
                HIGHESTMODSEQ=highestmodseq)

    return cache_validity

def uidvalidity_valid(crispin_client):
    """ Validate UIDVALIDITY on currently selected folder. """
    cached_validity = db_session.query(UIDValidity.uid_validity).filter_by(
            g_gmail=crispin_client.email_address,
            folder_name=crispin_client.selected_folder_name).one()[0]
    return crispin_client.selected_uidvalidity > cached_validity

def modseq_update(email):
    # XXX TODO: from this point on, we need to start checking UIDVALIDITY
    if not uidvalidity_valid(crispin_client):
        log.error(
        """The user's UIDVALIDITY value has changed. We need to do a UID
           refresh matching on X-GM-MSGIDs for existing messages and updating
           the MessageMeta tables. (No need to download messages all over
           again.""")
    cache_validity = load_validity_cache(crispin_client, email, SYNC_FOLDERS)
    # needs_update = []
    # for folder in SYNC_FOLDERS:
    #     # XXX eventually we might want to be holding a cache of this stuff
    #     # from any SELECT calls that have already happened, to save on a
    #     # status call.
    #     status = crispin_client.imap_server.folder_status(folder,
    #             ('UIDVALIDITY', 'HIGHESTMODSEQ'))
    #     if status['HIGHESTMODSEQ'] > cache_validity[folder]['HIGHESTMODSEQ']:
    #         needs_update.append(folder)
    # XXX finish this

    for folder in SYNC_FOLDERS:
        crispin_client.select_folder(folder)
        server_uids = crispin_client.all_uids()
        highestmodseq = crispin_client.selected_highestmodseq
        uidvalidity = crispin_client.selected_uidvalidity
        if highestmodseq > cache_validity[folder]['HIGHESTMODSEQ']:
            # XXX needs update
            pass

def initial_sync(user_email_address):
    """ Downloads entire messages and
    (1) creates the metadata database
    (2) stores message parts to the block store
    """
    crispin_client = refresh_crispin(user_email_address)
    # XXX TODO: need to check UIDVALIDITY here, for the case of initial sync
    # restarts

    log.info('Syncing mail for {0}'.format(user_email_address))

    # message download for messages from SYNC_FOLDERS is prioritized before
    # AllMail in the order of appearance in this list
    # XXX At some point we may want to query for a user's labels and sync
    # _all_ of them here. You can query gmail labels with
    # crispin_client.imap_server.list_folders() and filter out the [Gmail]
    # folders
    SYNC_FOLDERS = ['Inbox', crispin_client.all_mail_folder_name()]

    for folder in SYNC_FOLDERS:
        # for each folder, compare what's on the server to what we have.
        # this allows restarts of the initial sync script in the case of
        # total failure.
        crispin_client.select_folder(folder)
        highestmodseq = crispin_client.selected_highestmodseq
        uidvalidity = crispin_client.selected_uidvalidity
        server_uids = crispin_client.all_uids()
        server_g_msgids = crispin_client.fetch_g_msgids(server_uids)
        g_msgids = set([g_msgid for g_msgid, in
            db_session.query(distinct(FolderMeta.g_msgid))])

        log.info("Found {0} UIDs for folder {1}".format(
            len(server_uids), folder))
        existing_uids = [uid for uid, in
                db_session.query(FolderMeta.msg_uid).filter_by(
                    g_email=user_email_address, folder_name=folder)]
        log.info("Already have {0} items".format(len(existing_uids)))
        warn_uids = set(existing_uids).difference(set(server_uids))
        unknown_uids = set(server_uids).difference(set(existing_uids))

        # these will be dealt with later in HIGHESTMODSEQ updates, which
        # also checks for deleted messages
        # XXX TODO:  might as well delete these now? will save work later.
        for uid in warn_uids:
            log.error("{1} msg {0} doesn't exist on server".format(uid, folder))

        full_download, foldermeta_only = partition(
                lambda uid: server_g_msgids[uid] in g_msgids,
                sorted(unknown_uids, key=int))

        log.info("{0} uids left to fetch".format(len(full_download)))

        log.info("skipping {0} uids downloaded via other folders".format(
            len(foldermeta_only)))
        if len(foldermeta_only) > 0:
            db_session.add_all(
                    [crispin_client.make_fm(server_g_msgids[uid], folder,
                        uid) for uid in foldermeta_only])
            db_session.commit()

        total_messages = len(existing_uids)

        chunk_size = 20
        log.info("Starting sync for {0} with chunks of size {1}".format(
            folder, chunk_size))
        for uids in chunk(full_download, chunk_size):
            # log.info("Fetching from {0} to {1}".format(uids[0], uids[-1]))
            try:
                new_messagemeta, new_messagepart, new_foldermeta = \
                        crispin_client.fetch_uids(uids)
            except EncodingError, e:
                raise
            # XXX make this catch more specific
            except Exception, e:
                log.error("Crispin fetch failure: %s. Reconnecting..." % e)
                crispin_client = refresh_crispin(user_email_address)
                new_messagemeta, new_messagepart, new_foldermeta = \
                        crispin_client.fetch_uids(uids)

            db_session.add_all(new_foldermeta)
            db_session.add_all(new_messagemeta)
            db_session.add_all(new_messagepart)


            for m in new_messagepart:  # TODO do this via MessageMeta constructor?
                m.g_email = user_email_address

            try:
                db_session.commit()
            except sqlalchemy.exc.SQLAlchemyError, e:
                log.error(e.orig.args)
            except Exception, e:
                log.error("Unknown exception: %s" % e)

            total_messages += len(uids)

            pct = total_messages / len(server_uids) * 100
            sys.stdout.write("\r|%-73s| %.4f%%" % ('#' * int(pct*.73), pct) ),
            sys.stdout.flush()

        # transaction commit
        # if we've done a restart on the initial sync, we may have already
        # saved a UIDValidity row for any given folder, so we need to update
        # it instead. BUT, we first need to check for updated metadata since
        # the recorded UIDValidity, in case things like flags have changed.
        cached_validity = db_session.query(UIDValidity).filter_by(
                g_email=user_email_address, folder_name=folder).first()
        if cached_validity:
            # XXX TODO: do a HIGHESTMODSEQ update here to check for updated
            # metadata since the recorded UIDValidity.
            # XXX remove this UIDValidity update once we've finished the
            # above, since doing that update should also update the recorded
            # UIDValidity
            cached_validity.uid_validity = uidvalidity
            cached_validity.highestmodseq = highestmodseq
            db_session.add(cached_validity)
            db_session.commit()
        else:
            db_session.add(UIDValidity(
                g_email=user_email_address, folder_name=folder, uid_validity=uidvalidity,
                highestmodseq=highestmodseq))
            db_session.commit()
        print
        log.info("Saved all messages and metadata on {0} to UIDVALIDITY {1} / HIGHESTMODSEQ {2}".format(folder, uidvalidity, highestmodseq))

    print
    log.info("Finished.")

    # TODO: immediately start doing a HIGHESTMODSEQ search

    return 0

def main():
    parser = argparse.ArgumentParser(
            description="Download initial mail metadata and parts.")
    parser.add_argument('-u', '--user-email', dest='user_email', required=True)
    args = parser.parse_args()
    return initial_sync(args.user_email)

if __name__ == '__main__':
    sys.exit(main())
