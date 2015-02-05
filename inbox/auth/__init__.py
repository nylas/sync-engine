"""
Per-provider auth modules.

An auth module *must* meet the following requirement:

1. Specify the provider it implements as the module-level PROVIDER variable.
For example, 'gmail', 'imap', 'eas', 'yahoo' etc.

2. Live in the 'auth/' directory.

3. Register an AuthHandler class as an entry point in setup.py
"""
# Allow out-of-tree auth submodules.
from pkgutil import extend_path
from inbox.util.misc import register_backends
__path__ = extend_path(__path__, __name__)
module_registry = register_backends(__name__, __path__)
