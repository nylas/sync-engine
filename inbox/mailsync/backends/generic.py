"""
-----------------
GENERIC SYNC ENGINE
-----------------

IMAP backend with no CONDSTORE support.

For providers that not provide server-side threading, so we have to thread
messages ourselves. Currently we make each message its own thread.

Providers that do not currently support synchronizing flag changes. (We plan to
add support for this later, but a lack of CONDSTORE makes it tricky / slow.)

"""
from inbox.mailsync.backends.imap.imap_generic import ImapGenericSyncMonitor
__all__ = ['ImapGenericSyncMonitor']

PROVIDER = 'generic'
SYNC_MONITOR_CLS = 'ImapGenericSyncMonitor'
