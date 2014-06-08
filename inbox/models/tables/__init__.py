"""
Per-provider table modules.

A table module *must* meet the following requirement:

1. Live in the 'tables/' directory.
"""
# Allow out-of-tree table submodules.
from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
