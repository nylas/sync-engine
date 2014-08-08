"""
-----------------
GENERIC IMAP SYNC ENGINE (~WITH~ COND STORE)
-----------------

Generic IMAP backend with CONDSTORE support.

No support for server-side threading, so we have to thread messages ourselves.

"""
from inbox.crispin import retry_crispin
from inbox.mailsync.backends.imap import (condstore_base_poll,
                                          condstore_imap_initial_sync,
                                          resync_uids_from,
                                          base_initial_sync, ImapSyncMonitor,
                                          imap_create_message,
                                          generic_highestmodseq_update)


class ImapGenericCondstoreSyncMonitor(ImapSyncMonitor):
    def __init__(self, account_id, namespace_id, email_address, provider,
                 heartbeat=1, poll_frequency=30):
        self.folder_state_handlers = {
            'initial': initial_sync,
            'initial uidinvalid': resync_uids_from('initial'),
            'poll': poll,
            'poll uidinvalid': resync_uids_from('poll'),
            'finish': lambda c, s, l, f, st: 'finish',
        }

        ImapSyncMonitor.__init__(self, account_id, namespace_id, email_address,
                                 provider, heartbeat=1,
                                 poll_frequency=poll_frequency)


@retry_crispin
def poll(conn_pool, log, folder_name, shared_state):
    with conn_pool.get() as crispin_client:
        return condstore_base_poll(crispin_client,
                                   log,
                                   folder_name,
                                   shared_state,
                                   generic_highestmodseq_update)


@retry_crispin
def initial_sync(conn_pool, log, folder_name, shared_state):
    with conn_pool.get() as crispin_client:
        return base_initial_sync(crispin_client, log, folder_name,
                                 shared_state, condstore_imap_initial_sync,
                                 imap_create_message)
