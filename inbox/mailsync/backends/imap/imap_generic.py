"""
-----------------
GENERIC IMAP SYNC ENGINE (SANS COND STORE)
-----------------

Generic IMAP backend with no CONDSTORE support. Flags for recent messages are
updated on each poll, and periodically during initial sync.

No support for server-side threading, so we have to thread messages ourselves.
"""
from inbox.crispin import retry_crispin
from inbox.mailsync.backends.imap import (base_poll, imap_poll_update,
                                          resync_uids_from, base_initial_sync,
                                          imap_initial_sync, ImapSyncMonitor,
                                          update_metadata, imap_create_message)


class ImapGenericSyncMonitor(ImapSyncMonitor):
    def __init__(self, account_id, namespace_id, email_address, provider_name,
                 heartbeat=1, poll_frequency=30):
        self.folder_state_handlers = {
            'initial': initial_sync,
            'initial uidinvalid': resync_uids_from('initial'),
            'poll': poll,
            'poll uidinvalid': resync_uids_from('poll'),
            'finish': lambda c, s, l, f, st: 'finish',
        }

        ImapSyncMonitor.__init__(self, account_id, namespace_id, email_address,
                                 provider_name, heartbeat=1,
                                 poll_frequency=poll_frequency)


@retry_crispin
def poll(conn_pool, log, folder_name, shared_state):
    with conn_pool.get() as crispin_client:
        return base_poll(crispin_client, log, folder_name,
                         shared_state, imap_poll_update,
                         imap_create_message, update_metadata)


@retry_crispin
def initial_sync(conn_pool, log, folder_name, shared_state):
    with conn_pool.get() as crispin_client:
        return base_initial_sync(crispin_client, log, folder_name,
                                 shared_state, imap_initial_sync,
                                 imap_create_message)
