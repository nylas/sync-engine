"""
Per-provider table modules.

A table module *must* meet the following requirements:

1. Specify the provider it implements as the module-level PROVIDER variable.
For example, 'Imap', 'EAS' etc.

2. Live in the 'tables/' directory.
"""
# Allow out-of-tree auth submodules.
from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)