"""
-----------------
YAHOO SYNC ENGINE
-----------------

Yahoo is an IMAP backend with no CONDSTORE support.

Yahoo does not provide server-side threading, so we have to thread messages
ourselves. Currently we make each message its own thread.

Yahoo does not currently support synchronizing flag changes. (We plan to add
support for this later, but a lack of CONDSTORE makes it tricky / slow.)

"""
from inbox.mailsync.backends.imap.imap_generic import ImapGenericSyncMonitor
__all__ = ['ImapGenericSyncMonitor']

PROVIDER = 'yahoo'
SYNC_MONITOR_CLS = 'ImapGenericSyncMonitor'
