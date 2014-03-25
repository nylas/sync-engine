"""
Per-provider action modules.

An action module *must* meet the following requirement:

1. Specify the provider it implements as the module-level PROVIDER variable.
For example, 'Gmail', 'Imap', 'EAS', 'Yahoo' etc.

2. Live in the 'actions/' directory.
"""
# Allow out-of-tree action submodules.
from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
