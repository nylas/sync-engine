"""
Per-provider backend modules.

A backend module *must* meet the following requirements:

1. Specify the provider it implements as the module-level `PROVIDER` variable.
For example, 'gmail', 'imap', 'eas', 'yahoo' etc.

2. Implement a sync monitor class which inherits from the
BaseMailSyncMonitor class.

3. Specify the name of the sync monitor class as the module-level
`SYNC_MONITOR_CLASS` variable.

4. The module may install a submodule tree of arbitrary depth, but the
`PROVIDER` and `SYNC_MONITOR_CLS` variables must be defined in a direct
submodule of `backends`, and that top-level module must import the
referenced class.

"""
# Allow out-of-tree backend submodules.
from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)

from inbox.util.misc import register_backends

module_registry = register_backends(__name__, __path__)
