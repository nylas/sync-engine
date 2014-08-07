"""
-----------------
GENERIC IMAP SYNC ENGINE (SANS COND STORE)
-----------------

Generic IMAP backend with no CONDSTORE support. Flags for recent messages are
updated on each poll, and periodically during initial sync.

No support for server-side threading, so we have to thread messages ourselves.
Currently we make each message its own thread.

"""
from inbox.crispin import retry_crispin
from inbox.models.util import reconcile_message
from inbox.models.backends.imap import ImapThread
from inbox.mailsync.backends.imap import (account, base_poll, imap_poll_update,
                                          resync_uids_from, base_initial_sync,
                                          imap_initial_sync, ImapSyncMonitor,
                                          update_metadata)


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
                         create_message, update_metadata)


@retry_crispin
def initial_sync(conn_pool, log, folder_name, shared_state):
    with conn_pool.get() as crispin_client:
        return base_initial_sync(crispin_client, log, folder_name,
                                 shared_state, imap_initial_sync,
                                 create_message)


def create_message(db_session, log, acct, folder, msg):
    """ Message creation logic.

    Returns
    -------
    new_uid: inbox.models.backends.imap.ImapUid
        New db object, which links to new Message and Block objects through
        relationships. All new objects are uncommitted.
    """
    assert acct is not None and acct.namespace is not None

    new_uid = account.create_imap_message(db_session, log, acct, folder, msg)

    new_uid = add_attrs(db_session, log, new_uid, msg.flags, folder,
                        msg.created)
    return new_uid


def add_attrs(db_session, log, new_uid, flags, folder, created):
    """ Post-create-message bits."""
    with db_session.no_autoflush:
        new_uid.message.thread = ImapThread.from_imap_message(
            db_session, new_uid.account.namespace, new_uid.message)
        new_uid.update_imap_flags(flags)

        # make sure this thread has all the correct labels
        new_labels = account.update_thread_labels(new_uid.message.thread,
                                                  folder.name,
                                                  [folder.canonical_name],
                                                  db_session)

        # Reconciliation for Drafts, Sent Mail folders:
        if (('draft' in new_labels or 'sent' in new_labels) and not
                created and new_uid.message.inbox_uid):
            reconcile_message(db_session, log, new_uid.message.inbox_uid,
                              new_uid.message)

        return new_uid
