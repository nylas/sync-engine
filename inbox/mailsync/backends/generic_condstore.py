"""
----------------------------------
GENERIC SYNC ENGINE WITH CONDSTORE
----------------------------------

IMAP backend with CONDSTORE support.

For providers that not provide server-side threading, so we have to thread
messages ourselves. Currently we make each message its own thread.
"""
from inbox.mailsync.backends.imap.imap_condstore \
    import ImapGenericCondstoreSyncMonitor

__all__ = ['ImapGenericCondstoreSyncMonitor']

PROVIDER = 'generic_condstore'
SYNC_MONITOR_CLS = 'ImapGenericCondstoreSyncMonitor'
