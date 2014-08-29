from inbox.mailsync.backends.imap import common
from inbox.mailsync.backends.imap.monitor import ImapSyncMonitor

__all__ = ['common', 'ImapSyncMonitor']


PROVIDER = 'generic'
SYNC_MONITOR_CLS = 'ImapSyncMonitor'
