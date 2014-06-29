"""
Per-provider auth modules.

An auth module *must* meet the following requirement:

1. Specify the provider it implements as the module-level PROVIDER variable.
For example, 'gmail', 'imap', 'eas', 'yahoo' etc.

2. Live in the 'auth/' directory.
"""
# Allow out-of-tree auth submodules.
from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
