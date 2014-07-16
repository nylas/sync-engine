"""
-----------------
YAHOO SYNC ENGINE
-----------------

Yahoo is an IMAP backend with no CONDSTORE support. This may eventually be
our default generic IMAP implementation, but for now it's easier to develop
the backend separately.

Yahoo does not provide server-side threading, so we have to thread messages
ourselves. Currently we make each message its own thread.

Yahoo does not currently support synchronizing flag changes. (We plan to add
support for this later, but a lack of CONDSTORE makes it tricky / slow.)

"""
from inbox.crispin import retry_crispin
from inbox.models.util import reconcile_message
from inbox.models.backends.imap import ImapThread
from inbox.mailsync.backends.imap import (account, base_poll, imap_poll_update,
                                          resync_uids_from, base_initial_sync,
                                          imap_initial_sync, ImapSyncMonitor)


PROVIDER = 'yahoo'
SYNC_MONITOR_CLS = 'YahooSyncMonitor'


class YahooSyncMonitor(ImapSyncMonitor):
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
def poll(conn_pool, db_session, log, folder_name, shared_state):
    with conn_pool.get() as crispin_client:
        return base_poll(crispin_client, db_session, log, folder_name,
                         shared_state, imap_poll_update, create_yahoo_message)


@retry_crispin
def initial_sync(conn_pool, db_session, log, folder_name, shared_state):
    with conn_pool.get() as crispin_client:
        return base_initial_sync(crispin_client, db_session, log, folder_name,
                                 shared_state, imap_initial_sync,
                                 create_yahoo_message)


def create_yahoo_message(db_session, log, acct, folder, msg):
    """ Yahoo-specific message creation logic.

    Returns
    -------
    new_uid: inbox.models.backends.imap.ImapUid
        New db object, which links to new Message and Block objects through
        relationships. All new objects are uncommitted.
    """
    assert acct is not None and acct.namespace is not None

    new_uid = account.create_imap_message(db_session, log, acct, folder, msg)

    new_uid = add_yahoo_attrs(db_session, log, new_uid, msg.flags, folder,
                              msg.created)
    return new_uid


def add_yahoo_attrs(db_session, log, new_uid, flags, folder, created):
    """ Yahoo-specific post-create-message bits."""
    with db_session.no_autoflush:
        new_uid.message.thread = ImapThread.from_yahoo_message(
            db_session, new_uid.account.namespace, new_uid.message)
        new_uid.update_imap_flags(flags)

        if folder in ('draft', 'sent') and not created and new_uid.message.inbox_uid:
            reconcile_message(db_session, log, new_uid.message.inbox_uid,
                              new_uid.message)

        return new_uid
