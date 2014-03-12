"""
Per-provider backend modules.

A backend module *must* meet the following requirements:

1. Specify the provider it implements as the module-level PROVIDER variable.
For example, 'Gmail', 'Imap', 'EAS', 'Yahoo' etc.

2. Implement a sync monitor class which inherits from the
BaseMailSyncMonitor class.

3. Specify the name of the sync monitor class as the module-level
SYNC_MONITOR_CLASS variable.

4. Live either in the 'backends/' directory [OR] in an *immediate* subdirectory
of 'backends/'.
"""
